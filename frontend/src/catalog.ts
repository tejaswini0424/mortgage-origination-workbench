export const caseTools = [
  ["workspace", "Case workspace"],
  ["borrowers", "Borrowers"],
  ["timeline", "Case timeline"],
  ["upload", "Upload center"],
  ["documents", "Document library"],
  ["viewer", "Document viewer"],
  ["classification", "Classification"],
  ["fields", "Extracted fields"],
  ["checklist", "Document checklist"],
  ["field-review", "Field review"],
  ["discrepancies", "Discrepancies"],
  ["review-history", "Review history"],
  ["income", "Income worksheet"],
  ["assets", "Assets worksheet"],
  ["liabilities", "Liabilities worksheet"],
  ["scenario", "Loan scenario"],
  ["summary", "Case summary"],
  ["exports", "Exports"],
] as const;

export const catalog = [
  {
    name: "Overview",
    items: [
      ["/", "Dashboard"],
      ["/workflow", "Workflow overview"],
    ],
  },
  {
    name: "Cases",
    items: [
      ["/cases", "Case list"],
      ["/new", "New case"],
      ...caseTools.slice(0, 3).map(([key, label]) => ["/tools/" + key, label]),
    ],
  },
  {
    name: "Documents",
    items: caseTools
      .slice(3, 9)
      .map(([key, label]) => ["/tools/" + key, label]),
  },
  {
    name: "Human review",
    items: [
      ["/review", "Review queue"],
      ...caseTools.slice(9, 12).map(([key, label]) => ["/tools/" + key, label]),
    ],
  },
  {
    name: "Origination",
    items: caseTools.slice(12).map(([key, label]) => ["/tools/" + key, label]),
  },
  {
    name: "Research",
    items: [
      ["/benchmark-datasets", "Benchmark datasets"],
      ["/research", "Evaluation runs"],
      ["/model-comparison", "Model comparison"],
      ["/robustness", "Robustness analysis"],
    ],
  },
  {
    name: "Administration",
    items: [
      ["/audit", "Audit log"],
      ["/users", "User management"],
      ["/settings", "Settings"],
      ["/api-documentation", "API documentation"],
      ["/health", "System health"],
    ],
  },
];
