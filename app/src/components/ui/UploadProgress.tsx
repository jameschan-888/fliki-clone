type Props = {
  loaded: number;
  total: number;
  label?: string;
};

function formatMB(bytes: number): string {
  if (bytes < 1024) return bytes + " B";
  if (bytes < 1024 * 1024) return (bytes / 1024).toFixed(1) + " KB";
  return (bytes / 1024 / 1024).toFixed(2) + " MB";
}

export function UploadProgress({ loaded, total, label }: Props) {
  if (!total) return null;
  const pct = Math.min(100, Math.round((loaded / total) * 100));
  return (
    <div className="uploadProgressWrap">
      <div className="uploadProgressTrack">
        <div className="uploadProgressBar" style={{ width: pct + "%" }} />
      </div>
      <div className="uploadProgressMeta">
        <span>{label || "上传中"}</span>
        <span>{pct}% · {formatMB(loaded)} / {formatMB(total)}</span>
      </div>
    </div>
  );
}
