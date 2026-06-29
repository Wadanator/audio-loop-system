export default function SummaryCard({ title, value, detail, tone = 'neutral' }) {
  return (
    <article className={`summary-card summary-card-${tone}`}>
      <span className="summary-title">{title}</span>
      <strong className="summary-value">{value}</strong>
      <span className="summary-detail">{detail}</span>
    </article>
  );
}