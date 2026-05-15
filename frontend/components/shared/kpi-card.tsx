import { ReactNode } from "react";
import { cn } from "@/lib/utils";
import { Card, CardContent } from "@/components/ui/card";

interface KPICardProps {
  title: string;
  value: string | number;
  icon?: ReactNode;
  trend?: { value: string; positive?: boolean };
  subtitle?: string;
  className?: string;
}

export function KPICard({ title, value, icon, trend, subtitle, className }: KPICardProps) {
  return (
    <Card className={cn("card-hover", className)}>
      <CardContent className="p-5">
        <div className="flex items-start justify-between mb-3">
          <p className="kpi-label">{title}</p>
          {icon && <div className="text-primary/60">{icon}</div>}
        </div>
        <div className="kpi-value text-accent">{value}</div>
        {trend && (
          <p className={cn("text-xs mt-1 font-medium", trend.positive ? "text-green-600" : "text-red-600")}>
            {trend.value}
          </p>
        )}
        {subtitle && <p className="text-xs text-muted-foreground mt-1">{subtitle}</p>}
      </CardContent>
    </Card>
  );
}
