# Step 6 — Initialize the Working PPTX

`unpack.py` only accepts `.pptx`. If the template is `.potx`, convert
first:

```bash
if [[ "$TEMPLATE_FILE" == *.potx ]]; then
  PPTX_FILE="${TEMPLATE_FILE%.potx}.pptx"
  python $PPTX_SKILL/scripts/office/potx2pptx.py "$TEMPLATE_FILE" -o "$PPTX_FILE"
else
  PPTX_FILE="$TEMPLATE_FILE"
fi

python $PPTX_SKILL/scripts/office/unpack.py "$PPTX_FILE" unpacked/
```

All slide creation and editing in Steps 7–8 happens inside `unpacked/`.

**Checkpoint:** `unpacked/ppt/presentation.xml` exists.
