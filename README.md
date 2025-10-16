# MSTR Herald API

MicroStrategy Herald is a Flask-based REST API that provides data from MicroStrategy dossiers in a standardized JSON format with pagination support.

## Features

- Connect to MicroStrategy REST API
- Fetch reports with agency code filters
- API versioning (v1, v2)
- Response pagination
- Docker containerization
- Response caching
- Systemd service integration

## Quick Start

### Using Docker

```bash
# Clone the repository
git clone <repository-url>
cd mstr_herald

# Configure environment variables
cp .env.example .env
# Edit .env with your MicroStrategy credentials

# Start with Docker Compose
docker-compose up -d
```

### Manual Installation

```bash
# Clone the repository
git clone <repository-url>
cd mstr_herald

# Create and activate virtual environment
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt

# Configure environment variables
cp .env.example .env
# Edit .env with your MicroStrategy credentials

# Run the application
cd src
python app.py
```

## API Endpoints

### Health Check

```
GET /api/v1/ping
```

Returns `{"status": "ok"}` if the service is running.

### Get Report Data (v1)

```
GET /api/v1/report/{report_name}/agency/{agency_code}
```

Parameters:
- `report_name`: Report identifier from dossiers.yaml
- `agency_code`: Agency filter code
- `info_type` (query): Type of information to retrieve (default: "summary")
- `page` (query): Page number (default: 1)
- `page_size` (query): Items per page (default: 100)

### Get Report Data (v2)

```
GET /api/v2/report/{report_name}/agency/{agency_code}
```

Parameters: Same as v1.

## Available Reports

The following reports are configured in `src/config/dossiers.yaml`:

- p1_anlik_uretim
- p2_yenileme
- p3_acente_hedef
- p4_acente_karnesi
- p5_hasar
- p6_segmentasyon
- p8_ytd_uretim
- p8_mtd_uretim
- p9_kazançlarım
- p10_tekliflerim
- r1_yenileme_raporu
- r2_uretim_raporu
- r3_teklif_raporu

## Development

### Project Structure

```
.
├── docker-compose.yml    # Docker Compose configuration
├── Dockerfile            # Docker build configuration
├── mstr_herald.service   # Systemd service file
├── README.md             # This documentation
├── requirements.txt      # Python dependencies
└── src
    ├── app.py            # Main Flask application
    ├── config
    │   └── dossiers.yaml # MicroStrategy dossier configurations
    └── mstr_herald
        ├── connection.py # MicroStrategy connection management
        ├── fetcher.py    # Data fetching logic (v1)
        ├── fetcher_v2.py # Enhanced data fetching (v2)
        ├── __init__.py
        ├── selectors.py  # Utility for listing filter keys
        └── utils.py      # General utility functions
```

### Environment Variables

Create a `.env` file with the following variables:

```
# Flask
PORT=8000
CACHE_TYPE=SimpleCache
CACHE_TIMEOUT=60

# MicroStrategy
MSTR_URL_API=http://your-mstr-server:8080/MicroStrategyLibrary/api
MSTR_BASE_URL=http://your-mstr-server:8080
MSTR_USERNAME=your_username
MSTR_PASSWORD=your_password
MSTR_PROJECT=your_project
```

## Deployment

### Docker Deployment

```bash
docker-compose up -d
```

### Systemd Service Installation

```bash
# Copy service file
sudo cp mstr_herald.service /etc/systemd/system/

# Create mstrapp user (if not exists)
sudo useradd -r mstrapp

# Set up application directory
sudo mkdir -p /opt/mstr_herald
sudo cp -r . /opt/mstr_herald
sudo chown -R mstrapp:mstrapp /opt/mstr_herald

# Create virtual environment
sudo -u mstrapp python -m venv /opt/mstr_herald/venv
sudo -u mstrapp /opt/mstr_herald/venv/bin/pip install -r /opt/mstr_herald/requirements.txt

# Start and enable service
sudo systemctl daemon-reload
sudo systemctl start mstr_herald
sudo systemctl enable mstr_herald
```

## License

[Your license information]