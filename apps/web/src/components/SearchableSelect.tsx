"use client";

import { useMemo, useState } from "react";

export function SearchableSelect({
  label,
  options,
  value,
  onChange,
  placeholder = "Choose…",
}: {
  label?: string;
  options: string[];
  value: string;
  onChange: (v: string) => void;
  placeholder?: string;
}) {
  const [open, setOpen] = useState(false);
  const [filter, setFilter] = useState("");
  const [highlighted, setHighlighted] = useState(-1);
  const filtered = useMemo(
    () => options.filter((o) => o.toLowerCase().includes(filter.toLowerCase())),
    [options, filter]
  );

  const exactMatch = (v: string) =>
    options.find((opt) => opt.toLowerCase() === v.toLowerCase());

  const selectOption = (opt: string) => {
    onChange(opt);
    setFilter(opt);
    setOpen(false);
    setHighlighted(-1);
  };

  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (!open || !filter) return;
    if (e.key === "ArrowDown") {
      e.preventDefault();
      setHighlighted((prev) => Math.min(prev + 1, filtered.length - 1));
    } else if (e.key === "ArrowUp") {
      e.preventDefault();
      setHighlighted((prev) => Math.max(prev - 1, -1));
    } else if (e.key === "Enter") {
      e.preventDefault();
      if (highlighted >= 0 && filtered[highlighted]) {
        selectOption(filtered[highlighted]);
      } else if (exactMatch(filter)) {
        selectOption(exactMatch(filter)!);
      }
    } else if (e.key === "Escape") {
      setOpen(false);
      setHighlighted(-1);
    }
  };

  const handleBlur = () => {
    setTimeout(() => setOpen(false), 120);
  };

  const handleListMouseDown = (e: React.MouseEvent) => {
    e.preventDefault();
  };

  return (
    <label className="block">
      {label && <span className="eyebrow">{label}</span>}
      <div className="relative mt-2">
        <input
          type="text"
          className="field w-full px-3 py-2 text-sm pr-10"
          placeholder={placeholder}
          value={value || filter}
          onChange={(e) => {
            const v = e.target.value;
            setFilter(v);
            setHighlighted(-1);
            const match = exactMatch(v);
            if (match) onChange(match);
          }}
          onKeyDown={handleKeyDown}
          onFocus={() => setOpen(true)}
          onBlur={handleBlur}
          autoComplete="off"
        />
        {open && filter && (
          <ul
            className="absolute z-10 w-full mt-1 max-h-60 overflow-auto rounded-lg border border-warm-100/20 bg-ink-900/95 shadow-lg"
            role="listbox"
            onMouseDown={handleListMouseDown}
          >
            {filtered.length === 0 ? (
              <li className="px-3 py-2 text-[11px] text-parchment-400">No matches found</li>
            ) : (
              filtered.map((opt, idx) => (
                <li
                  key={opt}
                  role="option"
                  className={`px-3 py-2 text-sm cursor-pointer ${
                    idx === highlighted
                      ? "bg-copper-400/30 text-copper-100"
                      : opt === value
                      ? "bg-copper-400/20 text-copper-200"
                      : "text-parchment-200 hover:bg-warm-100/10"
                  }`}
                  onClick={() => selectOption(opt)}
                >
                  {opt}
                </li>
              ))
            )}
          </ul>
        )}
      </div>
    </label>
  );
}