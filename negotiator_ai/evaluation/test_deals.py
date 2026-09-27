"""
test_deals.py — 10 test deals for Phase 6 evaluation.

Each deal varies by: item type, deal size, and user leverage type
(first-time buyer / repeat customer / competing quotes) — per plan Section 6.
"""

TEST_DEALS = [
    # -----------------------------------------------------------------------
    # Deal 1: Packaging — Small — First-time buyer
    # -----------------------------------------------------------------------
    {
        "deal_id": "D01",
        "description": "Small packaging order, first-time buyer",
        "business_id": "eval_business",
        "business_name": "QuickShip Retail",
        "deal_facts": {
            "item": "Corrugated cardboard boxes (medium size)",
            "category": "packaging",
            "quantity": "200 units per month",
            "quoted_price": 45.0,
            "quoted_price_unit": "per unit",
            "payment_terms": "Net 30",
            "delivery_days": 7,
            "supplier_name": "BoxMart Suppliers",
            "industry": "Retail / E-commerce",
            "is_repeat_customer": False,
            "repeat_order_count": 0,
            "cumulative_spend": 0,
            "has_competing_quotes": False,
            "competing_quote_price": 0,
            "competing_quote_count": 0,
            "can_commit_volume": True,
            "commitment_months": 3,
            "urgency": "medium",
            "additional_context": "First order. Need reliable monthly supply.",
        },
    },

    # -----------------------------------------------------------------------
    # Deal 2: Packaging — Large — Repeat customer
    # -----------------------------------------------------------------------
    {
        "deal_id": "D02",
        "description": "Large packaging order, repeat customer with history",
        "business_id": "eval_business",
        "business_name": "QuickShip Retail",
        "deal_facts": {
            "item": "Custom-printed packaging boxes",
            "category": "packaging",
            "quantity": "1000 units per month",
            "quoted_price": 38.0,
            "quoted_price_unit": "per unit",
            "payment_terms": "Net 30",
            "delivery_days": 10,
            "supplier_name": "BoxMart Suppliers",
            "industry": "Retail / E-commerce",
            "is_repeat_customer": True,
            "repeat_order_count": 14,
            "cumulative_spend": 65000,
            "has_competing_quotes": False,
            "competing_quote_price": 0,
            "competing_quote_count": 0,
            "can_commit_volume": True,
            "commitment_months": 12,
            "urgency": "low",
            "additional_context": "14 orders over 18 months. Always paid on time. Want annual rate lock.",
        },
    },

    # -----------------------------------------------------------------------
    # Deal 3: Raw Ingredients (F&B) — Small — Competing quotes
    # -----------------------------------------------------------------------
    {
        "deal_id": "D03",
        "description": "Small F&B raw materials, 3 competing quotes",
        "business_id": "eval_business",
        "business_name": "Spice Garden Restaurant",
        "deal_facts": {
            "item": "Premium basmati rice (25 kg bags)",
            "category": "raw_materials",
            "quantity": "50 bags per month",
            "quoted_price": 1800.0,
            "quoted_price_unit": "per 25kg bag",
            "payment_terms": "Net 15",
            "delivery_days": 3,
            "supplier_name": "GrainCo Distributors",
            "industry": "F&B / Restaurant",
            "is_repeat_customer": False,
            "repeat_order_count": 0,
            "cumulative_spend": 0,
            "has_competing_quotes": True,
            "competing_quote_price": 1620.0,
            "competing_quote_count": 3,
            "can_commit_volume": True,
            "commitment_months": 6,
            "urgency": "medium",
            "additional_context": "3 competing quotes. Lowest at ₹1620/bag. Similar quality.",
        },
    },

    # -----------------------------------------------------------------------
    # Deal 4: Raw Ingredients (F&B) — Large — Repeat + competing
    # -----------------------------------------------------------------------
    {
        "deal_id": "D04",
        "description": "Large F&B order, repeat customer + competing quotes",
        "business_id": "eval_business",
        "business_name": "Spice Garden Restaurant",
        "deal_facts": {
            "item": "Refined sunflower oil (15L tins)",
            "category": "raw_materials",
            "quantity": "200 tins per month",
            "quoted_price": 2100.0,
            "quoted_price_unit": "per tin",
            "payment_terms": "Net 30",
            "delivery_days": 5,
            "supplier_name": "FoodOil Traders",
            "industry": "F&B / Restaurant",
            "is_repeat_customer": True,
            "repeat_order_count": 20,
            "cumulative_spend": 420000,
            "has_competing_quotes": True,
            "competing_quote_price": 1900.0,
            "competing_quote_count": 2,
            "can_commit_volume": True,
            "commitment_months": 12,
            "urgency": "low",
            "additional_context": "20 orders, ₹4.2L spend. 2 competing quotes at ₹1900. Want price lock for 12 months.",
        },
    },

    # -----------------------------------------------------------------------
    # Deal 5: Equipment Rental — Small — First-time buyer
    # -----------------------------------------------------------------------
    {
        "deal_id": "D05",
        "description": "Small equipment rental, first-time buyer",
        "business_id": "eval_business",
        "business_name": "BuildFast Contractors",
        "deal_facts": {
            "item": "Concrete mixer rental",
            "category": "equipment",
            "quantity": "1 unit for 2 months",
            "quoted_price": 18000.0,
            "quoted_price_unit": "per month",
            "payment_terms": "Advance payment",
            "delivery_days": 2,
            "supplier_name": "RentEquip Solutions",
            "industry": "Construction",
            "is_repeat_customer": False,
            "repeat_order_count": 0,
            "cumulative_spend": 0,
            "has_competing_quotes": False,
            "competing_quote_price": 0,
            "competing_quote_count": 0,
            "can_commit_volume": True,
            "commitment_months": 2,
            "urgency": "medium",
            "additional_context": "Need for 2-month project. First time renting from this company.",
        },
    },

    # -----------------------------------------------------------------------
    # Deal 6: Equipment Rental — Large — Repeat customer
    # -----------------------------------------------------------------------
    {
        "deal_id": "D06",
        "description": "Large equipment rental, repeat customer",
        "business_id": "eval_business",
        "business_name": "BuildFast Contractors",
        "deal_facts": {
            "item": "Scaffolding system (full set for 3-floor building)",
            "category": "equipment",
            "quantity": "3 sets for 6 months",
            "quoted_price": 45000.0,
            "quoted_price_unit": "per set per month",
            "payment_terms": "Net 15",
            "delivery_days": 3,
            "supplier_name": "RentEquip Solutions",
            "industry": "Construction",
            "is_repeat_customer": True,
            "repeat_order_count": 8,
            "cumulative_spend": 980000,
            "has_competing_quotes": False,
            "competing_quote_price": 0,
            "competing_quote_count": 0,
            "can_commit_volume": True,
            "commitment_months": 6,
            "urgency": "low",
            "additional_context": "8 rentals over 2 years. Nearly ₹10L cumulative. Want 6-month rate with delivery.",
        },
    },

    # -----------------------------------------------------------------------
    # Deal 7: Service/AMC Contract — Small — Competing quotes
    # -----------------------------------------------------------------------
    {
        "deal_id": "D07",
        "description": "AMC contract, small scope, competing quotes",
        "business_id": "eval_business",
        "business_name": "FreshFoods Market",
        "deal_facts": {
            "item": "Commercial refrigeration unit AMC (4 units)",
            "category": "service",
            "quantity": "Annual AMC for 4 refrigeration units",
            "quoted_price": 85000.0,
            "quoted_price_unit": "total annual",
            "payment_terms": "100% upfront",
            "delivery_days": 2,
            "supplier_name": "CoolTech Services",
            "industry": "Retail / Grocery",
            "is_repeat_customer": False,
            "repeat_order_count": 0,
            "cumulative_spend": 0,
            "has_competing_quotes": True,
            "competing_quote_price": 72000.0,
            "competing_quote_count": 2,
            "can_commit_volume": True,
            "commitment_months": 12,
            "urgency": "medium",
            "additional_context": "2 competing quotes at ₹72K. Equipment critical for operations.",
        },
    },

    # -----------------------------------------------------------------------
    # Deal 8: Cleaning Supplies — Large — First-time buyer
    # -----------------------------------------------------------------------
    {
        "deal_id": "D08",
        "description": "Large cleaning supplies, first-time commercial buyer",
        "business_id": "eval_business",
        "business_name": "Serene Hospitality",
        "deal_facts": {
            "item": "Commercial cleaning chemicals and supplies (monthly bundle)",
            "category": "office_supplies",
            "quantity": "Monthly bundle for 50-room hotel",
            "quoted_price": 28000.0,
            "quoted_price_unit": "per month",
            "payment_terms": "Net 15",
            "delivery_days": 3,
            "supplier_name": "CleanPro Distributors",
            "industry": "Hospitality / Hotel",
            "is_repeat_customer": False,
            "repeat_order_count": 0,
            "cumulative_spend": 0,
            "has_competing_quotes": False,
            "competing_quote_price": 0,
            "competing_quote_count": 0,
            "can_commit_volume": True,
            "commitment_months": 12,
            "urgency": "medium",
            "additional_context": "Moving from retail purchases to commercial supplier. Annual commitment possible.",
        },
    },

    # -----------------------------------------------------------------------
    # Deal 9: Office Furniture — Medium — Repeat customer
    # -----------------------------------------------------------------------
    {
        "deal_id": "D09",
        "description": "Office furniture bulk purchase, repeat buyer",
        "business_id": "eval_business",
        "business_name": "TechStartup Co.",
        "deal_facts": {
            "item": "Ergonomic office workstations (desk + chair combo)",
            "category": "office_supplies",
            "quantity": "25 workstations",
            "quoted_price": 22000.0,
            "quoted_price_unit": "per workstation",
            "payment_terms": "Net 30",
            "delivery_days": 14,
            "supplier_name": "OfficePro Furnishings",
            "industry": "Technology",
            "is_repeat_customer": True,
            "repeat_order_count": 3,
            "cumulative_spend": 150000,
            "has_competing_quotes": False,
            "competing_quote_price": 0,
            "competing_quote_count": 0,
            "can_commit_volume": True,
            "commitment_months": 0,
            "urgency": "low",
            "additional_context": "3rd purchase from this supplier. Growing team, may need more later.",
        },
    },

    # -----------------------------------------------------------------------
    # Deal 10: Logistics/Freight — Medium — Competing quotes
    # -----------------------------------------------------------------------
    {
        "deal_id": "D10",
        "description": "Logistics contract, competing quotes, volume commitment",
        "business_id": "eval_business",
        "business_name": "QuickShip Retail",
        "deal_facts": {
            "item": "Interstate freight service (B2B deliveries)",
            "category": "logistics",
            "quantity": "300+ shipments per month, interstate",
            "quoted_price": 380.0,
            "quoted_price_unit": "per shipment",
            "payment_terms": "Net 15",
            "delivery_days": 3,
            "supplier_name": "FastTrack Logistics",
            "industry": "Retail / E-commerce",
            "is_repeat_customer": False,
            "repeat_order_count": 0,
            "cumulative_spend": 0,
            "has_competing_quotes": True,
            "competing_quote_price": 320.0,
            "competing_quote_count": 3,
            "can_commit_volume": True,
            "commitment_months": 12,
            "urgency": "medium",
            "additional_context": "3 competing quotes. Best at ₹320/shipment. Want annual rate card.",
        },
    },
]

# Convenience lookup
DEAL_BY_ID = {d["deal_id"]: d for d in TEST_DEALS}

if __name__ == "__main__":
    print(f"Loaded {len(TEST_DEALS)} test deals")
    for d in TEST_DEALS:
        print(f"  {d['deal_id']}: {d['description']}")
