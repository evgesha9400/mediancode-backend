# Frontend Prompt: Change `parameterType` (string) to `parameterTypes` (string array)

## Context

The backend has changed the `field_constraints` entity:
- **Before:** `parameterType: string` — single value like `"int"`, `"str"`, or `"number"` (synthetic workaround)
- **After:** `parameterTypes: string[]` — array of actual Python types like `["int"]`, `["str"]`, or `["int", "float"]`

The API response key changed from `parameterType` to `parameterTypes`. The `"number"` value no longer exists — it's been replaced by `["int", "float"]`.

**New API response shape for `GET /v1/field-constraints`:**
```json
{
  "id": "uuid",
  "namespaceId": "uuid",
  "name": "max_length",
  "description": "...",
  "parameterTypes": ["int"],
  "docsUrl": "...",
  "compatibleTypes": ["str", "uuid"],
  "usedInFields": 3
}
```

**Value mapping (old → new):**
| Old `parameterType` | New `parameterTypes` |
|---|---|
| `"int"` | `["int"]` |
| `"str"` | `["str"]` |
| `"number"` | `["int", "float"]` |

## Files to modify

### 1. Type definition: `src/lib/types/index.ts`

**Line 191** — Change `FieldConstraintBase` interface:
```ts
// BEFORE
parameterType: string;

// AFTER
parameterTypes: string[];
```

### 2. API layer: `src/lib/api/fieldConstraints.ts`

**Lines 13-22** — Update `FieldConstraintResponse` interface:
```ts
// BEFORE
parameterType: string;

// AFTER
parameterTypes: string[];
```

**Lines 27-38** — Update `transformFieldConstraint` function:
```ts
// BEFORE
parameterType: response.parameterType,

// AFTER
parameterTypes: response.parameterTypes,
```

### 3. Store: `src/lib/stores/fieldConstraints.ts`

**Line 35** — Update `searchFieldConstraints` function. Change the search to search across array items:
```ts
// BEFORE
fieldConstraint.parameterType.toLowerCase().includes(lowerQuery)

// AFTER
fieldConstraint.parameterTypes.some(t => t.toLowerCase().includes(lowerQuery))
```

### 4. Component: `src/lib/components/api-generator/FieldConstraintEditor.svelte`

This is the most logic-heavy change. The editor uses `parameterType` to determine:
- Input type (text vs number)
- Step attribute (1 vs any)
- Placeholder text
- Badge display

**Line 19** — Update `onParamChange` callback signature:
```ts
// BEFORE
onParamChange: (index: number, rawValue: string, parameterType: string) => void;

// AFTER
onParamChange: (index: number, rawValue: string, parameterTypes: string[]) => void;
```

**Line 65** — Badge display. Change from single string to joined array:
```svelte
<!-- BEFORE -->
<span class="text-xs text-mono-500 bg-mono-100 px-2 py-0.5 rounded">{constraintMeta.parameterType}</span>

<!-- AFTER -->
<span class="text-xs text-mono-500 bg-mono-100 px-2 py-0.5 rounded">{constraintMeta.parameterTypes.join(', ')}</span>
```

**Lines 69-73** — Input type/step/placeholder logic. Change from single-string comparison to array `.includes()`:
```svelte
<!-- BEFORE -->
type={constraintMeta.parameterType === 'str' ? 'text' : 'number'}
step={constraintMeta.parameterType === 'int' ? '1' : 'any'}
oninput={(e) => onParamChange(index, e.currentTarget.value, constraintMeta.parameterType)}
placeholder={constraintMeta.parameterType === 'str' ? 'e.g. ^[a-z]+$' : 'Value'}

<!-- AFTER -->
type={constraintMeta.parameterTypes.includes('str') ? 'text' : 'number'}
step={constraintMeta.parameterTypes.includes('float') ? 'any' : '1'}
oninput={(e) => onParamChange(index, e.currentTarget.value, constraintMeta.parameterTypes)}
placeholder={constraintMeta.parameterTypes.includes('str') ? 'e.g. ^[a-z]+$' : 'Value'}
```

Note the step logic change: **before** it was `=== 'int' ? '1' : 'any'` (checking for int). **Now** it should be `includes('float') ? 'any' : '1'` (if float is in the list, allow decimals; otherwise integers only). This is because `["int", "float"]` should allow decimals, while `["int"]` should only allow whole numbers.

### 5. Component: `src/lib/components/api-generator/FieldConstraintSelectorDropdown.svelte`

**Line 31** — Search filtering. Change from string method to array:
```ts
// BEFORE
fc.parameterType.toLowerCase().includes(lowerQuery)

// AFTER
fc.parameterTypes.some(t => t.toLowerCase().includes(lowerQuery))
```

**Line 95** — Badge display:
```svelte
<!-- BEFORE -->
<span class="text-xs text-mono-500 bg-mono-100 px-2 py-0.5 rounded">{fc.parameterType}</span>

<!-- AFTER -->
<span class="text-xs text-mono-500 bg-mono-100 px-2 py-0.5 rounded">{fc.parameterTypes.join(', ')}</span>
```

### 6. Field Constraints list page: `src/routes/(dashboard)/validators/field-constraints/+page.svelte`

**Lines 149-153** — Table column header. Change the sort column key and label:
```svelte
<!-- BEFORE -->
<SortableColumn
  column="parameterType"
  label="Parameter Type"
  {sorts}
  onSort={state.handleSort}
/>

<!-- AFTER -->
<SortableColumn
  column="parameterTypes"
  label="Parameter Types"
  {sorts}
  onSort={state.handleSort}
/>
```

**Lines 196-199** — Table cell. Render as chips/tags (same as `compatibleTypes`):
```svelte
<!-- BEFORE -->
<td class="px-6 py-4 whitespace-nowrap">
  <span class="px-2 py-0.5 text-xs rounded-full bg-mono-200 text-mono-700">
    {fc.parameterType}
  </span>
</td>

<!-- AFTER -->
<td class="px-6 py-4">
  <div class="flex flex-wrap gap-1">
    {#each fc.parameterTypes as ptype}
      <span class="px-2 py-0.5 text-xs rounded-full bg-mono-200 text-mono-700">
        {ptype}
      </span>
    {/each}
  </div>
</td>
```

**Lines 283-287** — Drawer detail section. Change label and render as chips:
```svelte
<!-- BEFORE -->
<div>
  <h3 class="text-sm text-mono-500 mb-1 font-medium">Parameter Type</h3>
  <code class="px-2 py-1 text-xs rounded bg-mono-100 text-mono-800 font-mono">
    {selectedFieldConstraint.parameterType}
  </code>
</div>

<!-- AFTER -->
<div>
  <h3 class="text-sm text-mono-500 mb-1 font-medium">Parameter Types</h3>
  <div class="flex flex-wrap gap-1.5 mt-1">
    {#each selectedFieldConstraint.parameterTypes as ptype}
      <code class="px-2 py-1 text-xs rounded bg-mono-100 text-mono-800 font-mono">
        {ptype}
      </code>
    {/each}
  </div>
</div>
```

### 7. Fields page: `src/routes/(dashboard)/fields/+page.svelte`

**Line 124** — `updateConstraintParam` function signature. The `parameterType` parameter is accepted but unused. Change it to `parameterTypes` for consistency:
```ts
// BEFORE
function updateConstraintParam(index: number, rawValue: string, parameterType: string) {

// AFTER
function updateConstraintParam(index: number, rawValue: string, parameterTypes: string[]) {
```

### 8. Test fixtures: `tests/fixtures/seedData.ts`

Update all 8 field constraint entries. Change `parameterType` key to `parameterTypes` with array values:

```ts
// String constraints
{ name: 'max_length', ..., parameterTypes: ['int'], ... }
{ name: 'min_length', ..., parameterTypes: ['int'], ... }
{ name: 'pattern', ..., parameterTypes: ['str'], ... }

// Numeric constraints (these were "number" before — now explicit list)
{ name: 'gt', ..., parameterTypes: ['int', 'float'], ... }
{ name: 'ge', ..., parameterTypes: ['int', 'float'], ... }
{ name: 'lt', ..., parameterTypes: ['int', 'float'], ... }
{ name: 'le', ..., parameterTypes: ['int', 'float'], ... }
{ name: 'multiple_of', ..., parameterTypes: ['int', 'float'], ... }
```

### 9. Test file: `tests/integration/routes/dashboard/page.test.ts`

**Line 111** — Property check:
```ts
// BEFORE
expect(fc).toHaveProperty('parameterType');

// AFTER
expect(fc).toHaveProperty('parameterTypes');
```

**Lines 137-143** — Validation test. Update to check array type:
```ts
// BEFORE
it('field constraints have valid parameterType values', () => {
  const fieldConstraints = get(fieldConstraintsStore);
  fieldConstraints.forEach((fc) => {
    expect(typeof fc.parameterType).toBe('string');
    expect(fc.parameterType.length).toBeGreaterThan(0);
  });
});

// AFTER
it('field constraints have valid parameterTypes values', () => {
  const fieldConstraints = get(fieldConstraintsStore);
  fieldConstraints.forEach((fc) => {
    expect(Array.isArray(fc.parameterTypes)).toBe(true);
    expect(fc.parameterTypes.length).toBeGreaterThan(0);
  });
});
```

### 10. Page object: `tests/page-objects/FieldConstraintsPage.ts`

**Line 34** — Rename property:
```ts
// BEFORE
readonly parameterTypeColumnHeader: Locator;

// AFTER
readonly parameterTypesColumnHeader: Locator;
```

**Line 75** — Update locator text:
```ts
// BEFORE
this.parameterTypeColumnHeader = this.table.locator('thead th').filter({ hasText: 'Parameter Type' });

// AFTER
this.parameterTypesColumnHeader = this.table.locator('thead th').filter({ hasText: 'Parameter Types' });
```

**Lines 253-258** — Update `sortByColumn` method:
```ts
// BEFORE
async sortByColumn(column: 'name' | 'parameterType' | 'usedInFields', ...) {
  const headerMap = {
    ...
    parameterType: () => this.table.locator('thead th button').filter({ hasText: 'Parameter Type' }),
    ...
  };

// AFTER
async sortByColumn(column: 'name' | 'parameterTypes' | 'usedInFields', ...) {
  const headerMap = {
    ...
    parameterTypes: () => this.table.locator('thead th button').filter({ hasText: 'Parameter Types' }),
    ...
  };
```

### 11. Test fixtures schema doc: `tests/fixtures/SCHEMA.md`

**Line 103** — Update the field description:
```md
<!-- BEFORE -->
parameterType: string;              // Type of parameter expected (int, str, number)

<!-- AFTER -->
parameterTypes: string[];           // Types of parameter expected (e.g. ["int"], ["int", "float"])
```

**Line 263** — Update the reference:
```md
<!-- BEFORE -->
   - Field constraint parameters match `parameterType`

<!-- AFTER -->
   - Field constraint parameters match `parameterTypes`
```

## Verification

After making all changes:
1. Run `npm run check` (or `pnpm check`) to verify TypeScript compiles
2. Run tests to verify fixtures and integration tests pass
3. Manually verify the field constraints list page renders array chips instead of single strings
4. Verify the field editor correctly shows number/text inputs based on array contents
5. Search the entire codebase for any remaining `parameterType` references (should be zero outside of comments/docs)
