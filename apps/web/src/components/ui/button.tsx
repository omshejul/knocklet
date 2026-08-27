import { Button as ButtonPrimitive } from "@base-ui/react/button"
import { cva, type VariantProps } from "class-variance-authority"
import { LoaderCircle } from "lucide-react"

import { cn } from "@/lib/utils"

const buttonVariants = cva(
  "group/button inline-flex shrink-0 items-center justify-center rounded-lg border border-transparent bg-clip-padding text-sm font-normal whitespace-nowrap transition-[filter,color,border-color,box-shadow,transform] outline-none select-none focus-visible:border-ring focus-visible:ring-3 focus-visible:ring-ring/50 active:not-aria-[haspopup]:translate-y-px disabled:pointer-events-none disabled:opacity-50 aria-invalid:border-destructive aria-invalid:ring-3 aria-invalid:ring-destructive/20 dark:aria-invalid:border-destructive/50 dark:aria-invalid:ring-destructive/40 [&_svg]:pointer-events-none [&_svg]:shrink-0 [&_svg:not([class*='size-'])]:size-4",
  {
    variants: {
      variant: {
        default:
          "border-primary/70 bg-[linear-gradient(to_bottom,var(--button-primary-top),var(--button-primary-bottom))] text-primary-foreground shadow-[inset_0_1px_0_rgba(255,255,255,0.95),0_1px_0_rgba(255,255,255,0.16),0_3px_8px_rgba(0,0,0,0.5)] hover:brightness-105 active:shadow-[inset_0_2px_4px_rgba(0,0,0,0.2),0_1px_2px_rgba(0,0,0,0.6)]",
        outline:
          "border-input bg-[linear-gradient(to_bottom,var(--button-surface-top),var(--button-surface-bottom))] text-foreground shadow-[inset_0_1px_0_rgba(255,255,255,0.12),0_1px_0_rgba(255,255,255,0.08),0_3px_8px_rgba(0,0,0,0.45)] hover:brightness-110 active:shadow-[inset_0_2px_4px_rgba(0,0,0,0.45),0_1px_2px_rgba(0,0,0,0.6)]",
        secondary:
          "border-input bg-[linear-gradient(to_bottom,var(--button-surface-top),var(--button-surface-bottom))] text-secondary-foreground shadow-[inset_0_1px_0_rgba(255,255,255,0.12),0_1px_0_rgba(255,255,255,0.08),0_3px_8px_rgba(0,0,0,0.45)] hover:brightness-110 active:shadow-[inset_0_2px_4px_rgba(0,0,0,0.45),0_1px_2px_rgba(0,0,0,0.6)]",
        ghost:
          "hover:bg-muted hover:text-foreground aria-expanded:bg-muted aria-expanded:text-foreground dark:hover:bg-muted/50",
        destructive:
          "border-destructive/60 bg-[linear-gradient(to_bottom,var(--button-destructive-top),var(--button-destructive-bottom))] text-white shadow-[inset_0_1px_0_rgba(255,255,255,0.2),0_1px_0_rgba(255,255,255,0.08),0_3px_8px_rgba(0,0,0,0.5)] hover:brightness-110 focus-visible:ring-destructive/40 active:shadow-[inset_0_2px_4px_rgba(0,0,0,0.35),0_1px_2px_rgba(0,0,0,0.6)]",
        link: "text-primary underline-offset-4 hover:underline",
      },
      size: {
        default:
          "h-8 gap-1.5 px-2.5 has-data-[icon=inline-end]:pr-2 has-data-[icon=inline-start]:pl-2",
        xs: "h-6 gap-1 rounded-[min(var(--radius-md),10px)] px-2 text-xs in-data-[slot=button-group]:rounded-lg has-data-[icon=inline-end]:pr-1.5 has-data-[icon=inline-start]:pl-1.5 [&_svg:not([class*='size-'])]:size-3",
        sm: "h-7 gap-1 rounded-[min(var(--radius-md),12px)] px-2.5 text-[0.8rem] in-data-[slot=button-group]:rounded-lg has-data-[icon=inline-end]:pr-1.5 has-data-[icon=inline-start]:pl-1.5 [&_svg:not([class*='size-'])]:size-3.5",
        lg: "h-9 gap-1.5 px-2.5 has-data-[icon=inline-end]:pr-2 has-data-[icon=inline-start]:pl-2",
        icon: "size-8",
        "icon-xs":
          "size-6 rounded-[min(var(--radius-md),10px)] in-data-[slot=button-group]:rounded-lg [&_svg:not([class*='size-'])]:size-3",
        "icon-sm":
          "size-7 rounded-[min(var(--radius-md),12px)] in-data-[slot=button-group]:rounded-lg",
        "icon-lg": "size-9",
      },
    },
    defaultVariants: {
      variant: "default",
      size: "default",
    },
  }
)

function Button({
  className,
  variant = "default",
  size = "default",
  loading = false,
  disabled,
  children,
  "aria-busy": ariaBusy,
  ...props
}: ButtonPrimitive.Props &
  VariantProps<typeof buttonVariants> & { loading?: boolean }) {
  return (
    <ButtonPrimitive
      data-slot="button"
      className={cn(buttonVariants({ variant, size, className }))}
      {...props}
      disabled={disabled || loading}
      aria-busy={loading || ariaBusy}
    >
      {children}
      {loading ? (
        <LoaderCircle className="animate-spin" aria-hidden="true" />
      ) : null}
    </ButtonPrimitive>
  )
}

export { Button, buttonVariants }
