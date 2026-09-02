# Working notes

Strategy and design, kept beside the code rather than in anyone's head. `PRODUCT_v2.md` at the
repository root is the product definition these serve; this directory is the detail under it.

| File | What it is | Read when |
|---|---|---|
| `01-PRODUCT.md` | Thesis, the loop, the four things the product does, card types | Before writing any prompt or UI copy |
| `02-SCOPE.md` | The priority ladder, the cut list, the degrade rule | Every time you consider adding something |
| `03-EVAL_DESIGN.md` | Metrics, case matrix, gold format, protocol | Before labelling or running anything |
| `04-CODE_AUDIT.md` | Verified defects in the first implementation, and the determinism landmines | While porting anything out of `reference/` |

`03-EVAL_DESIGN.md` is the most valuable file here: the eleven frozen cases and the scorer it
specifies are how you will know whether any future change helps.
