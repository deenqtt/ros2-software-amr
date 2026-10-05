import { cva, type VariantProps } from 'class-variance-authority'

/**
 * Button geometry follows DESIGN.md: every interactive control is a pill
 * (rounded.pill / 100px), sharp corners absent. Heights are one step down
 * from the marketing scale — 36px rather than 44px — for console density.
 *
 * Variants map onto the reference's documented set:
 *   primary   -> button-primary        (Coinbase Blue, the single voltage)
 *   secondary -> button-secondary-light (surface-strong fill)
 *   outline   -> button-outline-on-dark (transparent + hairline)
 *   ghost     -> no direct equivalent; toolbar affordance
 *   text      -> button-tertiary-text  (blue inline link)
 *   danger    -> see note below
 *
 * `danger` is a departure. The reference says never to use its semantic red
 * as a button fill, because there red only ever means "price down". Here red
 * means "this stops a moving machine", and an emergency control has to be the
 * loudest thing on screen. The rule is kept where it was aimed: semantic
 * status text stays colour-only and is never filled.
 */
export const buttonVariants = cva(
  'inline-flex items-center justify-center gap-xs whitespace-nowrap rounded-control font-sans font-semibold ' +
    'transition-colors duration-150 ease-out ' +
    'disabled:pointer-events-none [&_svg]:pointer-events-none [&_svg]:shrink-0 ' +
    // A fingertip needs 44px; a mouse does not. See the touch variant.
    'touch:min-h-[44px]',
  {
    variants: {
      variant: {
        primary: 'bg-primary text-on-primary hover:bg-primary-active disabled:bg-primary-disabled',
        secondary:
          'bg-surface-strong text-ink hover:bg-hairline disabled:text-muted-soft disabled:opacity-60',
        outline:
          'border border-hairline bg-transparent text-ink hover:bg-surface-strong disabled:text-muted-soft disabled:opacity-60',
        ghost: 'bg-transparent text-body hover:bg-surface-strong hover:text-ink disabled:opacity-40',
        text: 'bg-transparent px-0 text-primary hover:text-primary-active disabled:text-muted-soft',
        danger: 'bg-status-fault text-white hover:brightness-110 disabled:bg-surface-strong disabled:text-muted-soft',
      },
      size: {
        default: 'h-control px-base text-body-md',
        sm: 'h-control-sm px-sm text-body-sm',
        icon: 'h-control w-control p-0 touch:min-w-[44px]',
        'icon-sm': 'h-control-sm w-control-sm p-0 touch:min-w-[44px]',
      },
    },
    defaultVariants: { variant: 'primary', size: 'default' },
  },
)

export type ButtonVariants = VariantProps<typeof buttonVariants>
