type Props = { message: string };
export function Toast({ message }: Props) {
  if (!message) return null;
  return <div className="toast">{message}</div>;
}