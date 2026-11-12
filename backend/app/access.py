import getpass
import hashlib
import hmac
import os
import re
import secrets

from fastapi import HTTPException
from sqlalchemy import select

from .storage import Account, Case, CaseGrant, Organization, Session

def hash_password(password, salt=None):
    salt = salt or secrets.token_bytes(16)
    digest = hashlib.scrypt(password.encode(), salt=salt, n=2**14, r=8, p=1)
    return f"{salt.hex()}:{digest.hex()}"

DUMMY_HASH = hash_password("timing placeholder")

def authenticate(username, password):
    with Session() as db:
        account = db.get(Account, username)
        stored = account.password_hash if account and account.active else DUMMY_HASH
        match = hmac.compare_digest(hash_password(password, bytes.fromhex(stored.split(":")[0])), stored)
        return user_info(account) if match and account and account.active else None

def user_info(account):
    return {"username": account.username, "role": account.role, "organization": account.organization, "active": account.active}

def bootstrap():
    with Session.begin() as db:
        if db.get(Organization, "demo") is None:
            db.add(Organization(slug="demo", name="Demonstration workspace"))
            db.flush()
        for role in ("reviewer", "processor", "admin"):
            password = os.getenv(f"{role.upper()}_PASSWORD")
            if password and db.get(Account, role) is None:
                db.add(Account(username=role, organization="demo", role=role, password_hash=hash_password(password)))

def scope(user):
    organization = Case.organization == user["organization"]
    if user["role"] == "admin":
        return organization
    assigned = select(CaseGrant.case_id).where(CaseGrant.username == user["username"])
    return organization & ((Case.owner == user["username"]) | Case.id.in_(assigned))

def authorized_case(db, identifier, user, lock=False):
    query = select(Case).where(Case.id == identifier, scope(user))
    if lock:
        query = query.with_for_update()
    case = db.scalar(query)
    if case is None:
        raise HTTPException(404, "Record not found.")
    return case

def main():
    import argparse
    parser = argparse.ArgumentParser(description="Provision an organization administrator")
    parser.add_argument("organization")
    parser.add_argument("username")
    args = parser.parse_args()
    if not re.fullmatch(r"[a-z0-9][a-z0-9-]{0,63}", args.organization) or not re.fullmatch(r"[a-zA-Z0-9_.-]{1,120}", args.username):
        parser.error("Enter a valid organization slug and username.")
    password = getpass.getpass()
    if not 12 <= len(password) <= 200:
        parser.error("Use a password between 12 and 200 characters.")
    with Session.begin() as db:
        if db.get(Account, args.username):
            parser.error("That username already exists.")
        if db.get(Organization, args.organization) is None:
            db.add(Organization(slug=args.organization, name=args.organization))
            db.flush()
        db.add(Account(username=args.username, organization=args.organization, role="admin", password_hash=hash_password(password)))

if __name__ == "__main__":
    main()
