import type { ActionItemStatus } from "@/app/lib/api/types";

const STATUS_OPTIONS: Array<{ value: ActionItemStatus | ""; label: string }> = [
  { value: "", label: "All statuses" },
  { value: "open", label: "Open" },
  { value: "in_progress", label: "In progress" },
  { value: "done", label: "Done" },
];

interface ActionItemFiltersProps {
  owners: string[];
  status: ActionItemStatus | "";
  owner: string;
  onStatusChange: (status: ActionItemStatus | "") => void;
  onOwnerChange: (owner: string) => void;
}

const selectClassName =
  "rounded-full border border-border bg-surface-solid/80 px-3 py-1.5 text-xs text-foreground outline-none focus:border-accent/50 focus:ring-2 focus:ring-accent/30";

export function ActionItemFilters({
  owners,
  status,
  owner,
  onStatusChange,
  onOwnerChange,
}: ActionItemFiltersProps) {
  return (
    <div className="flex flex-wrap gap-2">
      <select
        aria-label="Filter action items by status"
        value={status}
        onChange={(event) => onStatusChange(event.target.value as ActionItemStatus | "")}
        className={selectClassName}
      >
        {STATUS_OPTIONS.map((option) => (
          <option key={option.value} value={option.value}>
            {option.label}
          </option>
        ))}
      </select>
      <select
        aria-label="Filter action items by owner"
        value={owner}
        onChange={(event) => onOwnerChange(event.target.value)}
        className={selectClassName}
      >
        <option value="">All owners</option>
        {owners.map((ownerName) => (
          <option key={ownerName} value={ownerName}>
            {ownerName}
          </option>
        ))}
      </select>
    </div>
  );
}
