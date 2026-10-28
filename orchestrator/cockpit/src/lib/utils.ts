import { clsx, type ClassValue } from "clsx";
import { twMerge } from "tailwind-merge";

/** Classes Tailwind conditionnelles, la dernière l’emporte en cas de conflit (convention shadcn/ui). */
export function cn(...entrees: ClassValue[]) {
  return twMerge(clsx(entrees));
}
