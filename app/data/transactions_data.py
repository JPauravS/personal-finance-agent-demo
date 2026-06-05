"""Embedded transaction data — generated from transactions.json.

Cloudflare Python Workers bundle .py modules but NOT arbitrary data files,
so banking_tools._load() falls back to this module when the JSON file is
absent at the edge. Regenerate after editing transactions.json:
    py -c "import json;rows=json.load(open(chr(39)+'app/data/transactions.json'+chr(39)));..."
Keep in sync with transactions.json (the canonical source + test fixture).
"""

TRANSACTIONS = [
    {'id': 't01', 'date': '2026-04-03', 'merchant': 'Zomato', 'category': 'food', 'amount': 2500.0, 'type': 'debit'},
    {'id': 't02', 'date': '2026-04-11', 'merchant': 'Swiggy', 'category': 'food', 'amount': 2400.0, 'type': 'debit'},
    {'id': 't03', 'date': '2026-04-19', 'merchant': 'Dominos', 'category': 'food', 'amount': 2300.0, 'type': 'debit'},
    {'id': 't04', 'date': '2026-04-27', 'merchant': 'Cafe Coffee Day', 'category': 'food', 'amount': 2400.0, 'type': 'debit'},
    {'id': 't05', 'date': '2026-05-02', 'merchant': 'Zomato', 'category': 'food', 'amount': 3000.0, 'type': 'debit'},
    {'id': 't06', 'date': '2026-05-09', 'merchant': 'Swiggy', 'category': 'food', 'amount': 3200.0, 'type': 'debit'},
    {'id': 't07', 'date': '2026-05-17', 'merchant': 'Dominos', 'category': 'food', 'amount': 2900.0, 'type': 'debit'},
    {'id': 't08', 'date': '2026-05-25', 'merchant': 'Faasos', 'category': 'food', 'amount': 2900.0, 'type': 'debit'},
    {'id': 't09', 'date': '2026-05-06', 'merchant': 'BookMyShow', 'category': 'entertainment', 'amount': 1500.0, 'type': 'debit'},
    {'id': 't10', 'date': '2026-05-15', 'merchant': 'Netflix', 'category': 'entertainment', 'amount': 1500.0, 'type': 'debit'},
    {'id': 't11', 'date': '2026-05-24', 'merchant': 'PVR', 'category': 'entertainment', 'amount': 1500.0, 'type': 'debit'},
    {'id': 't12', 'date': '2026-04-08', 'merchant': 'Amazon', 'category': 'shopping', 'amount': 4000.0, 'type': 'debit'},
    {'id': 't13', 'date': '2026-04-22', 'merchant': 'Flipkart', 'category': 'shopping', 'amount': 4000.0, 'type': 'debit'},
    {'id': 't14', 'date': '2026-05-08', 'merchant': 'Amazon', 'category': 'shopping', 'amount': 5000.0, 'type': 'debit'},
    {'id': 't15', 'date': '2026-05-21', 'merchant': 'Myntra', 'category': 'shopping', 'amount': 3000.0, 'type': 'debit'},
    {'id': 't16', 'date': '2026-04-14', 'merchant': 'Uber', 'category': 'travel', 'amount': 3500.0, 'type': 'debit'},
    {'id': 't17', 'date': '2026-05-14', 'merchant': 'Ola', 'category': 'travel', 'amount': 3500.0, 'type': 'debit'},
    {'id': 't18', 'date': '2026-04-05', 'merchant': 'BigBasket', 'category': 'groceries', 'amount': 3000.0, 'type': 'debit'},
    {'id': 't19', 'date': '2026-04-20', 'merchant': 'DMart', 'category': 'groceries', 'amount': 3000.0, 'type': 'debit'},
    {'id': 't20', 'date': '2026-05-05', 'merchant': 'BigBasket', 'category': 'groceries', 'amount': 3100.0, 'type': 'debit'},
    {'id': 't21', 'date': '2026-05-20', 'merchant': 'DMart', 'category': 'groceries', 'amount': 3100.0, 'type': 'debit'},
    {'id': 't22', 'date': '2026-04-28', 'merchant': 'Electricity Board', 'category': 'utilities', 'amount': 3000.0, 'type': 'debit'},
    {'id': 't23', 'date': '2026-05-28', 'merchant': 'Electricity Board', 'category': 'utilities', 'amount': 3000.0, 'type': 'debit'},
    {'id': 't24', 'date': '2026-05-01', 'merchant': 'Acme Payroll', 'category': 'transfers', 'amount': 50000.0, 'type': 'credit'},
]
