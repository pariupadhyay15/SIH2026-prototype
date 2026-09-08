

MOCK_COMPLIANCE_DB = {
    "PROD-EARBUDS": {
        "product_id": "PROD-EARBUDS",
        "product_name": "ProSound Wireless Earbuds",
        "category": "Consumer Electronics (CRS)",
        "applicable_standard": (
            "IS/IEC 62368-1:2023 / IS 16046:2018"  # Updated unified MeitY audio/IT standard
        ),
        "manufacturer": "Apex Electronics Ltd.",
        "steps": [
            {
                "step": 1,
                "title": "Coin Cell Battery Safety Test",
                "status": "Completed",
                "details": (
                    "Button Li-ion battery safety report generated under IS"
                    " 16046."
                ),
            },
            {
                "step": 2,
                "title": "Safety & EMC Lab Report",
                "status": "In Progress",
                "details": (
                    "Acoustic and electrical safety testing underway at NABL"
                    " lab."
                ),
            },
            {
                "step": 3,
                "title": "CRS Portal R-Number Allotment",
                "status": "Pending",
                "details": (
                    "Final self-declaration submission pending on BIS CRS"
                    " portal."
                ),
            },
        ],
    },
    "PROD-SPEAKER": {
        "product_id": "PROD-SPEAKER",
        "product_name": "BoomBox 20W Bluetooth Speaker",
        "category": "Consumer Electronics (CRS)",
        "applicable_standard": (
            "IS/IEC 62368-1:2023 (Audio & Video Safety)"  # Updated unified MeitY standard
        ),
        "manufacturer": "Apex Electronics Ltd.",
        "steps": [
            {
                "step": 1,
                "title": "Thermal & Insulation Safety",
                "status": "Completed",
                "details": (
                    "High-voltage and thermal stress testing passed at BIS"
                    " recognized lab."
                ),
            },
            {
                "step": 2,
                "title": "Power Adapter Validation",
                "status": "Completed",
                "details": (
                    "Linked certified bundled charging adapter (CRS valid)."
                ),
            },
            {
                "step": 3,
                "title": "CRS Self-Declaration Grant",
                "status": "In Progress",
                "details": (
                    "Application submitted; awaiting final digital officer"
                    " sign-off."
                ),
            },
        ],
    },
    "PROD-SMARTWATCH": {
        "product_id": "PROD-SMARTWATCH",
        "product_name": "PulseFit v2 Smartwatch",
        "category": "Wearable IT Equipment (CRS + WPC)",
        "applicable_standard": "IS/IEC 62368-1:2023 / WPC ETA Approval",
        "manufacturer": "Apex Electronics Ltd.",
        "steps": [
            {
                "step": 1,
                "title": "Wearable Li-Po Battery Safety",
                "status": "Completed",
                "details": (
                    "Curved Li-Po cell thermal pressure & leakage test"
                    " verified."
                ),
            },
            {
                "step": 2,
                "title": "WPC ETA Spectrum Clearance",
                "status": "In Progress",
                "details": (
                    "Equipment Type Approval submitted for Bluetooth 5.3"
                    " module."
                ),
            },
            {
                "step": 3,
                "title": "BIS Registration & E-Labeling",
                "status": "Pending",
                "details": (
                    "Configuring digital R-Number e-label display in UI"
                    " settings."
                ),
            },
        ],
    },
}