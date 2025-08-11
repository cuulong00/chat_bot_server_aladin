ACCOUNTING_DOMAIN = {
    "domain_context": "accounting, finance, bookkeeping, tax, compliance",
    "domain_instructions": (
        "Always prioritize accuracy and compliance. Use official accounting standards. "
        "If the question is about tax, double-check the latest regulations."
    ),
    "domain_examples": [
        "How to close the books at month-end?",
        "What is the VAT rate in Vietnam?",
        "How to record a fixed asset purchase?",
    ],
    "regulatory_requirements": "IFRS, VAS, local tax laws",
    "collection_name": "accounting_store",
    "namespace": "accounting_demo",
    "embedding_model": "models/text-embedding-004",
    "output_dimensionality_query": 768
}

INSURANCE_DOMAIN = {
    "domain_context": "insurance, policies, claims, underwriting, premiums, coverage, life insurance, health insurance, auto insurance, property insurance",
    "domain_instructions": (
        "Always explain policy terms clearly and simply. When discussing claims, outline the process step-by-step. "
        "Do not provide financial advice, only information about policy products. "
        "Verify coverage details based on the specific policy information provided."
    ),
    "domain_examples": [
        "How do I file a claim for my car accident?",
        "What is the difference between term life and whole life insurance?",
        "What does 'deductible' mean in my health insurance policy?",
    ],
    "regulatory_requirements": "Law on Insurance Business (Vietnam), local insurance regulations, consumer protection laws",
    "collection_name": "insurance_store",
    "namespace": "insurance_demo",
    "embedding_model": "models/text-embedding-004",
    "output_dimensionality_query": 768
}

WOLT_FOOD = {
    "domain_context": "Wolt, delivery, platform, restaurants, shops, courier partners, food delivery, grocery delivery, retail delivery, orders, online ordering, app, Helsinki, DoorDash",
    "domain_instructions": (
        "Focus on providing information about Wolt's services, functionality, and features. "
        "Explain how the platform connects customers, merchants, and couriers. "
        "Mention the types of deliveries Wolt facilitates, including food, groceries, and retail. "
        "Do not provide specific financial advice or details about courier earnings. "
        "Keep explanations clear and concise."
    ),
    "domain_examples": [
        "What is Wolt?",
        "How does Wolt delivery work?",
        "What kind of shops can I order from on Wolt?",
        "How can I become a Wolt courier partner?",
        "Does Wolt deliver groceries?",
    ],
    "regulatory_requirements": "Consumer protection laws, local delivery service regulations, food safety regulations (where applicable to food delivery)",
    "collection_name": "wolt_food_data",
    "namespace": "wolt_food_demo",
    "embedding_model": "models/text-embedding-004",
    "output_dimensionality_query": 512
}
