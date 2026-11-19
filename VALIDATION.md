# Validation

- All 12 automated tests passed with Python 3.12 and the pinned dependencies.
- The Outfitters collection sample had 40 cards for 20 distinct articles. The parser deduplicated color cards and found the next Ajaxinate page. The product sample's Shopify ID matched the live product JSON, which returned eight variants. A simulated stock and price change produced the correct Outfitters links and email heading.
- The live Outfitters cart reported PKR. The live dry run reached the eighth collection page before the 100 second test window ended. A full live scan still needs verification on GitHub Actions.
- The workflow's restore and persist steps ran against a temporary Git remote. They created the state branch, added Outfitters alongside the existing Khushposh files, and restored and updated each baseline independently.
- The Khushposh parser was previously checked against its supplied collection and product samples and live numbered pagination. A full live Khushposh scan also remains to be verified.
- Resend requests were mocked. Live delivery and deployment to GitHub remain to be verified.
