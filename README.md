# gunscraper 🔍 
> _A data scraping and analysis toolkit for firearm marketplace listings_

### by [`@zudsniper`](https://github.com/zudsniper)

## ABSTRACT
This project provides tools for scraping and analyzing firearm marketplace listings to understand market trends, pricing patterns, and product distributions. It uses AI-powered scraping to extract structured data from listings and provides statistical analysis of the results.

## Components

### Scraper (`scrape.py`)
The scraper component handles data collection:
- Intelligent pagination handling
- Crash recovery and resume capability
- Progress tracking and caching
- Structured data extraction using AI

### Data Models (`models.py`)
Defines the data structures for:
- Listings and previews
- Firearms and accessories
- Price and condition information
- Marketplace metadata

### Analysis (`parse.py`)
Provides statistical analysis including:
- Price distribution and trends
- Popular manufacturers and models
- Listing patterns and characteristics
- Market composition analysis

## Usage

1. Set up environment:
```bash
python -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

2. Configure API keys:
```bash
cp .env.example .env
# Edit .env with your OpenRouter API key
```

3. Run the scraper:
```bash
python scrape.py
```

4. Analyze results:
```bash
python parse.py
```

## Data Structure
The project uses Pydantic models to ensure data consistency:
- `ListingPreview`: Basic listing information
- `Gun`: Detailed firearm specifications
- `ListingsPages`: Collection of scraped pages

## Output Files
- `scraping_results.json`: Raw scraped data
- `listing_analysis.json`: Statistical analysis results
- `page_count_cache.json`: Pagination cache

## Contributing
Contributions are welcome! Please feel free to submit a Pull Request.

## License
This project is licensed under the MIT License - see the LICENSE file for details.

## Disclaimer
This tool is for market research purposes only. Users are responsible for complying with all applicable laws and regulations regarding firearms data collection and analysis.

---

<sub>v1.0.0</sub>
