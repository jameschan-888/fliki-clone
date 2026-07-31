import { formatApiError } from "../../api/autoedit";

type Props = {
  error: unknown;
  fallback?: string;
};

export function InlineError({ error, fallback = "操作失败" }: Props) {
  if (!error) return null;
  const msg = formatApiError(error, fallback);
  const hint = (error as { hint?: string })?.hint;
  return (
    <div className="errorBox" role="alert">
      <div className="errorMsg">{msg}</div>
      {hint && <div className="errorHint">{hint}</div>}
    </div>
  );
}
