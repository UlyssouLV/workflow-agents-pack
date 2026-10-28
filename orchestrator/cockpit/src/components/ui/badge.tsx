import { Slot } from "@radix-ui/react-slot";
import { cva, type VariantProps } from "class-variance-authority";
import type { ComponentProps } from "react";
import { cn } from "@/lib/utils";

/** Pastille d’état : une variante par couleur du code couleur (attention, agent, pilote…). */
const badgeVariants = cva(
  "inline-flex w-fit shrink-0 items-center gap-1.5 overflow-hidden rounded-full border px-2 py-px text-xs font-medium whitespace-nowrap no-underline [&>svg]:pointer-events-none [&>svg]:size-3",
  {
    variants: {
      variant: {
        neutre: "border-neutre/40 bg-neutre/15 text-foreground/80",
        attention: "border-attention/40 bg-attention/15 text-attention",
        agent: "border-agent/40 bg-agent/15 text-agent",
        pilote: "border-pilote/40 bg-pilote/15 text-pilote",
        pause: "border-dashed border-pilote/40 bg-pilote/10 text-pilote opacity-75",
        succes: "border-succes/40 bg-succes/15 text-succes",
        echec: "border-echec/40 bg-echec/15 text-echec",
      },
    },
    defaultVariants: { variant: "neutre" },
  },
);

function Badge({
  className,
  variant,
  asChild = false,
  ...props
}: ComponentProps<"span"> & VariantProps<typeof badgeVariants> & { asChild?: boolean }) {
  const Comp = asChild ? Slot : "span";
  return <Comp data-slot="badge" className={cn(badgeVariants({ variant }), className)} {...props} />;
}

/** Point de couleur ; `vivant` ajoute l’onde (coupée sous `prefers-reduced-motion`). */
function Pastille({
  className,
  vivant = false,
  ...props
}: ComponentProps<"span"> & { vivant?: boolean }) {
  return (
    <span data-slot="pastille" aria-hidden className={cn("relative inline-flex size-2 shrink-0", className)} {...props}>
      {vivant && <span className="absolute inset-0 animate-ping rounded-full bg-current opacity-60" />}
      <span className="relative inline-flex size-2 rounded-full bg-current" />
    </span>
  );
}

export { Badge, Pastille, badgeVariants };
