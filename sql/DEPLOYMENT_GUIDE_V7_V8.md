# SOFEM MES Deployment Guide - Schema v7 & v8
**Date**: April 1, 2026  
**Goal**: Deploy frozen pricing snapshots and immutable invoice system

---

## Overview

**Schema v7**: Frozen Pricing Infrastructure
- ✅ Adds `prix_vente_ht` to products table
- ✅ Creates `prix_historique` table for audit trail
- ✅ Creates `fa_lignes` table for immutable invoice lines
- ✅ Creates `of_costs` table for cost tracking
- ✅ Adds `produit_prix_snapshot` to ordres_fabrication

**Schema v8**: Complete Invoice Snapshot System
- ✅ Creates `of_invoice_snapshot` table (NEW)
- ✅ Captures ALL revenue and cost data at OF creation/completion
- ✅ Adds `of_id` column to factures_achat for sales invoices
- ✅ Captures estimated costs at OF creation
- ✅ Captures actual costs at OF completion

---

## Deployment Steps

### Step 1: Run Schema v7 in MySQL Workbench

1. Open MySQL Workbench
2. Connect to your sofem_mes database
3. Open file: `sql/schema_v7_frozen_pricing.sql`
4. Execute (⚡ button or Ctrl+Shift+Enter)
5. Verify: No errors appear

**Expected Output**: Schema v7 applied successfully

---

### Step 2: Run Schema v8 in MySQL Workbench

1. In MySQL Workbench, open file: `sql/schema_v8_of_invoice_snapshot.sql`
2. Execute (⚡ button or Ctrl+Shift+Enter)
3. Verify: No errors appear

**Expected Output**: Schema v8 applied successfully

---

### Step 3: Verify Tables Created

Run this query in MySQL Workbench to verify:

```sql
-- Check v7 tables
SELECT TABLE_NAME FROM INFORMATION_SCHEMA.TABLES 
WHERE TABLE_SCHEMA='sofem_mes' AND TABLE_NAME IN (
  'prix_historique', 'fa_lignes', 'of_costs'
);

-- Check v8 tables
SELECT TABLE_NAME FROM INFORMATION_SCHEMA.TABLES 
WHERE TABLE_SCHEMA='sofem_mes' AND TABLE_NAME IN (
  'of_invoice_snapshot'
);

-- Check v8 column added
SELECT COLUMN_NAME FROM INFORMATION_SCHEMA.COLUMNS 
WHERE TABLE_SCHEMA='sofem_mes' AND TABLE_NAME='factures_achat' 
AND COLUMN_NAME='of_id';
```

**Expected Results**:
- ✅ `prix_historique` table exists
- ✅ `fa_lignes` table exists
- ✅ `of_costs` table exists
- ✅ `of_invoice_snapshot` table exists
- ✅ `factures_achat.of_id` column exists

---

### Step 4: Restart Backend

1. Stop backend (Ctrl+C in terminal)
2. Restart backend:
   ```powershell
   python backend/main.py
   ```
3. Verify: Backend starts without errors

---

### Step 5: Test End-to-End Workflow

**Test Scenario**:

1. **Create new OF** (or use existing)
   - System auto-captures product price snapshot
   - System calculates estimated material & labor costs
   - Data stored in `of_invoice_snapshot`

2. **Complete OF**
   - Complete all operations
   - System calculates actual material & labor costs
   - Updates `of_invoice_snapshot` with `snapshot_at_completion`

3. **Create Sales Invoice**
   - POST `/api/achats/fa` with `of_id` (not `bc_id`)
   - System reads frozen snapshot
   - Invoice created with locked-in price

4. **Verify Snapshot**
   - Query: `SELECT * FROM of_invoice_snapshot WHERE of_id=123;`
   - Should show:
     - ✅ `produit_prix_unitaire` (frozen at creation)
     - ✅ `montant_vente_ht` (frozen)
     - ✅ `cost_materiel_estime/reel` (costs)
     - ✅ `cost_main_oeuvre_estime/reel` (labor)
     - ✅ `marge_brute_estime/reel` (margins)
     - ✅ `snapshot_at_creation` (timestamp)
     - ✅ `snapshot_at_completion` (timestamp)

---

## Expected Behavior After Deployment

### ✅ Frozen Pricing
- Create OF_1 with product price = 100 DT
- Change product price to 200 DT
- OF_1's snapshot still shows 100 DT (frozen)
- New OF_2 shows 200 DT (newly created)

### ✅ Cost Tracking
- OF created: System estimates material cost from BOM
- OF created: System estimates labor cost from operations
- OF completed: System calculates actual costs
- Margins show both estimated and actual

### ✅ Immutable Invoices
- Create sales invoice from OF snapshot
- Price locked forever
- Change OF price? Facture unchanged (reads frozen snapshot)

---

## Troubleshooting

| Issue | Solution |
|-------|----------|
| "Table already exists" | All CREATE statements are idempotent (IF NOT EXISTS) |
| "Column already exists" | ALTER statements skip if column already added |
| "Foreign key error" | Check that ordres_fabrication, produits, users tables exist |
| "Index error" | Already fixed - DROP before CREATE |

---

## Files Modified

Backend code ready for deployment:
- ✅ `backend/routes/of/of.py` - Captures snapshot at creation
- ✅ `backend/routes/of/operations.py` - Finalizes snapshot at completion
- ✅ `backend/routes/achats/fa.py` - Creates sales invoices from snapshot
- ✅ `backend/models.py` - Updated FACreate for of_id

Database schemas ready:
- ✅ `sql/schema_v7_frozen_pricing.sql` - Infrastructure
- ✅ `sql/schema_v8_of_invoice_snapshot.sql` - Complete snapshots

---

## Rollback (if needed)

If you need to rollback, use your database backup:
```sql
-- Restore from backup
mysql -u root -p sofem_mes < Dump20260401.sql
```

---

## Next Steps

1. ✅ Deploy schema_v7
2. ✅ Deploy schema_v8
3. ✅ Restart backend
4. ✅ Test workflow: Create OF → Complete → Create FA
5. Monitor logs for: "OF created with snapshot" and "OF completed: costs finalized"

---

**Status**: Ready to deploy ✅  
**Questions?** Check logs or run verification query above
