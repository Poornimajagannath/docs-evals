---
title: POST /v1/accounts
---

# POST /v1/accounts

**Method:** `POST`  
**Path:** `/v1/accounts`

| Name | Required | Description |
| --- | --- | --- |
| country | True | Two-letter country code |
| controller[fees][payer] | True | Who pays Stripe fees |
| controller[losses][payments] | True | Liability for negative balances |
| controller[stripe_dashboard][type] | True | Dashboard access type |

Auth: Bearer `sk_test_...`
