interface PageHeaderProps {
  title: string;
  subtitle?: string;
  right?: React.ReactNode;
}

export default function PageHeader({ title, subtitle, right }: PageHeaderProps) {
  return (
    <div
      className="flex items-center justify-between px-6 py-3.5 bg-white border-b border-[#E5E7EB]"
      style={{ minHeight: "52px" }}
    >
      <div>
        <h1 className="text-[15px] font-semibold text-[#111827]">{title}</h1>
        {subtitle && (
          <p className="text-[11px] text-[#9CA3AF] mt-0.5">{subtitle}</p>
        )}
      </div>
      {right && <div className="flex items-center gap-2">{right}</div>}
    </div>
  );
}
