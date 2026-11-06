import { useEffect, useId, useRef, useState } from "react";
import { createPortal } from "react-dom";
import {
  searchLocations,
  resolveLocation,
  type LocationFieldState,
  type Suggestion,
  type SelectedLocation,
} from "../lib/locations";
interface Props {
  label: string;
  value: LocationFieldState;
  onChange: (value: LocationFieldState) => void;
  disabled?: boolean;
  error?: string;
  onMap?: () => void;
  search?: typeof searchLocations;
  resolve?: typeof resolveLocation;
}
export function LocationAutocomplete({
  label,
  value,
  onChange,
  disabled,
  error,
  onMap,
  search = searchLocations,
  resolve = resolveLocation,
}: Props) {
  const id = useId(),
    input = useRef<HTMLInputElement>(null),
    popup = useRef<HTMLDivElement>(null);
  const [focused, setFocused] = useState(false),
    [open, setOpen] = useState(false),
    [items, setItems] = useState<Suggestion[]>([]),
    [active, setActive] = useState(-1),
    [busy, setBusy] = useState(false),
    [failure, setFailure] = useState(""),
    [retry, setRetry] = useState(0);
  const [position, setPosition] = useState({
    left: 0,
    top: 0,
    width: 0,
    maxHeight: 260,
  });
  const session = useRef(crypto.randomUUID()),
    revision = useRef(0),
    pending = useRef<AbortController | null>(null);
  const cache = useRef(new Map<string, Suggestion[]>());
  function stop() {
    revision.current++;
    pending.current?.abort();
    setBusy(false);
  }
  function dismiss() {
    stop();
    setOpen(false);
    setFocused(false);
    setActive(-1);
  }
  useEffect(() => {
    stop();
    setItems([]);
    setActive(-1);
    setFailure("");
    if (
      !focused ||
      value.selected ||
      disabled ||
      value.query.trim().length < 2
    ) {
      setOpen(false);
      return;
    }
    const controller = new AbortController();
    pending.current = controller;
    const version = revision.current;
    const timer = setTimeout(
      () => {
        setOpen(true);
        setBusy(true);
        const query = value.query.trim();
        void (
          cache.current.has(query)
            ? Promise.resolve(cache.current.get(query)!)
            : search(query, session.current, controller.signal)
        )
          .then((results) => {
            if (controller.signal.aborted || version !== revision.current)
              return;
            if (cache.current.size >= 20) cache.current.clear();
            cache.current.set(query, results);
            setItems(results);
          })
          .catch(() => {
            if (!controller.signal.aborted && version === revision.current)
              setFailure(
                "Cannot search locations. Check your connection and retry.",
              );
          })
          .finally(() => {
            if (!controller.signal.aborted && version === revision.current)
              setBusy(false);
          });
      },
      cache.current.has(value.query.trim()) ? 0 : 250,
    );
    return () => {
      clearTimeout(timer);
      controller.abort();
    };
  }, [value, focused, disabled, retry, search]);
  useEffect(() => {
    if (!open) return;
    const update = () => {
      const r = input.current?.getBoundingClientRect();
      if (r) {
        const below = window.innerHeight - r.bottom - 8,
          above = r.top - 8;
        const height = Math.min(280, Math.max(below, above));
        setPosition({
          left: Math.max(8, Math.min(r.left, window.innerWidth - r.width - 8)),
          top:
            below >= Math.min(220, above)
              ? r.bottom + 4
              : Math.max(8, r.top - height - 4),
          width: Math.min(r.width, window.innerWidth - 16),
          maxHeight: height,
        });
      }
    };
    const outside = (event: PointerEvent) => {
      if (
        !input.current?.contains(event.target as Node) &&
        !popup.current?.contains(event.target as Node)
      )
        dismiss();
    };
    update();
    window.addEventListener("resize", update);
    window.addEventListener("scroll", update, true);
    document.addEventListener("pointerdown", outside);
    return () => {
      window.removeEventListener("resize", update);
      window.removeEventListener("scroll", update, true);
      document.removeEventListener("pointerdown", outside);
    };
  }, [open]);
  useEffect(
    () => () => {
      revision.current++;
      pending.current?.abort();
    },
    [],
  );
  async function choose(item: Suggestion) {
    stop();
    const version = revision.current,
      controller = new AbortController();
    pending.current = controller;
    setBusy(true);
    setFailure("");
    try {
      const selected: SelectedLocation = await resolve(
        item,
        session.current,
        controller.signal,
      );
      if (controller.signal.aborted || version !== revision.current) return;
      onChange({ query: selected.label, selected });
      setOpen(false);
      setFocused(false);
      setItems([]);
      session.current = crypto.randomUUID();
      cache.current.clear();
      input.current?.focus();
    } catch {
      if (!controller.signal.aborted && version === revision.current)
        setFailure(
          "This place could not be resolved. Retry or choose another suggestion.",
        );
    } finally {
      if (!controller.signal.aborted && version === revision.current)
        setBusy(false);
    }
  }
  return (
    <div className="field location-field">
      <label htmlFor={id}>{label}</label>
      <div className="location-input">
        <input
          ref={input}
          id={id}
          role="combobox"
          autoComplete="off"
          aria-autocomplete="list"
          aria-expanded={open}
          aria-controls={id + "-list"}
          aria-activedescendant={
            open && active >= 0 ? id + "-option-" + active : undefined
          }
          aria-invalid={!!error}
          aria-describedby={id + "-status"}
          value={value.query}
          disabled={disabled}
          placeholder="Search city, address or place"
          onFocus={() => setFocused(true)}
          onBlur={dismiss}
          onChange={(e) => {
            stop();
            setFocused(true);
            onChange({ query: e.target.value, selected: null });
          }}
          onKeyDown={(e) => {
            if (e.key === "Escape") {
              e.preventDefault();
              dismiss();
            }
            if (e.key === "Tab") dismiss();
            if (
              (e.key === "ArrowDown" || e.key === "ArrowUp") &&
              items.length
            ) {
              e.preventDefault();
              setOpen(true);
              setActive((i) =>
                e.key === "ArrowDown"
                  ? (i + 1) % items.length
                  : i <= 0
                    ? items.length - 1
                    : i - 1,
              );
            }
            if (e.key === "Enter" && open) {
              e.preventDefault();
              if (active >= 0 && !busy) void choose(items[active]);
            }
          }}
        />
        {value.query && (
          <button
            type="button"
            className="location-clear"
            aria-label={"Clear " + label.toLowerCase()}
            disabled={disabled}
            onClick={() => {
              dismiss();
              onChange({ query: "", selected: null });
              input.current?.focus();
            }}
          >
            ×
          </button>
        )}
      </div>
      <span
        id={id + "-status"}
        className={error ? "field-error" : "field-help"}
        role="status"
      >
        {error ||
          (value.selected
            ? "✓ Location confirmed"
            : value.query
              ? "Select a location from the suggestions."
              : "Search and select a place.")}
      </span>
      {onMap && (
        <button
          type="button"
          className="text-button map-choice"
          disabled={disabled}
          onClick={() => {
            dismiss();
            onMap();
          }}
        >
          Choose {label.toLowerCase()} on map
        </button>
      )}
      {open &&
        createPortal(
          <div
            ref={popup}
            className="location-popup"
            style={{ position: "fixed", ...position }}
            onMouseDown={(e) => e.preventDefault()}
          >
            <div role="status" className="field-help">
              {busy
                ? "Finding location…"
                : failure ||
                  (!items.length
                    ? "No places found. Try a more specific search."
                    : "Choose a place")}
            </div>
            {failure && (
              <button
                type="button"
                onClick={() => {
                  cache.current.clear();
                  setRetry((v) => v + 1);
                }}
              >
                Retry location search
              </button>
            )}
            <ul
              role="listbox"
              id={id + "-list"}
              aria-label={label + " suggestions"}
            >
              {items.map((item, i) => (
                <li
                  role="option"
                  id={id + "-option-" + i}
                  key={item.id}
                  aria-selected={active === i}
                  onPointerMove={() => setActive(i)}
                  onClick={() => {
                    if (!busy) void choose(item);
                  }}
                >
                  <span aria-hidden="true">⌖</span>
                  <span>
                    <strong>{item.title}</strong>
                    <small>{item.subtitle}</small>
                  </span>
                </li>
              ))}
            </ul>
          </div>,
          document.body,
        )}
    </div>
  );
}
