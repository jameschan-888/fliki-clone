export function Spinner({ small = false }: { small?: boolean }) {
  return <span className={"spinner" + (small ? " small" : "")} aria-label="loading" />;
}