import { cva, type VariantProps } from "class-variance-authority";
import type { HTMLAttributes } from "react";

import { cn } from "@/lib/utils";

const alertVariants = cva("relative w-full rounded-lg border px-4 py-3 text-sm", {
  variants: {
    variant: {
      default: "bg-card text-card-foreground",
      destructive: "border-destructive/40 bg-card text-destructive",
    },
  },
  defaultVariants: {
    variant: "default",
  },
});

type AlertProps = HTMLAttributes<HTMLDivElement> & VariantProps<typeof alertVariants>;

function Alert({ className, variant, ...props }: AlertProps) {
  return <div role="alert" className={cn(alertVariants({ variant }), className)} {...props} />;
}

function AlertTitle({ className, ...props }: HTMLAttributes<HTMLHeadingElement>) {
  return <h3 className={cn("mb-1 font-medium leading-none", className)} {...props} />;
}

function AlertDescription({ className, ...props }: HTMLAttributes<HTMLDivElement>) {
  return <div className={cn("text-sm [&_p]:leading-relaxed", className)} {...props} />;
}

export { Alert, AlertDescription, AlertTitle };
