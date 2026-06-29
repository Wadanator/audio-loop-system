export default function ButtonGroup({ children, className = '' }) {
  return <div className={`button-group ${className}`}>{children}</div>;
}