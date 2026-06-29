export default function PageHeader({ title, subtitle, icon: Icon, children }) {
  return (
    <div className="page-header-container">
      <div className="page-header-left">
        {Icon && (
          <div className="page-header-icon-box">
            <Icon size={28} />
          </div>
        )}
        <div className="page-header-titles">
          <h1 className="page-title">{title}</h1>
          {subtitle && <p className="page-subtitle">{subtitle}</p>}
        </div>
      </div>

      {children && <div className="page-header-actions">{children}</div>}
    </div>
  );
}