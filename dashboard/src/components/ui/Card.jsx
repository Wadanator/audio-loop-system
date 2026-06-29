export default function Card({ children, title, icon: Icon, className = '', actions }) {
  return (
    <div className={`card-component ${className}`}>
      {(title || Icon || actions) && (
        <div className="card-header">
          <h3 className="card-title">
            {Icon && <Icon size={20} />}
            {title}
          </h3>
          {actions && <div className="card-actions">{actions}</div>}
        </div>
      )}

      <div className="card-content">
        {children}
      </div>
    </div>
  );
}