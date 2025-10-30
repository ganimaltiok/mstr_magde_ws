#!/bin/bash
# Install Microsoft ODBC Driver 18 for SQL Server on Ubuntu 24.04

set -e

echo "=== Installing Microsoft ODBC Driver 18 for SQL Server ==="
echo ""

# Add Microsoft repository
echo "[1/5] Adding Microsoft repository..."
curl https://packages.microsoft.com/keys/microsoft.asc | sudo tee /etc/apt/trusted.gpg.d/microsoft.asc

curl https://packages.microsoft.com/config/ubuntu/$(lsb_release -rs)/prod.list | sudo tee /etc/apt/sources.list.d/mssql-release.list

# Update package list
echo ""
echo "[2/5] Updating package list..."
sudo apt-get update

# Install ODBC Driver
echo ""
echo "[3/5] Installing ODBC Driver 18..."
sudo ACCEPT_EULA=Y apt-get install -y msodbcsql18

# Install optional tools (sqlcmd, bcp)
echo ""
echo "[4/5] Installing SQL Server command-line tools (optional)..."
sudo ACCEPT_EULA=Y apt-get install -y mssql-tools18
echo 'export PATH="$PATH:/opt/mssql-tools18/bin"' >> ~/.bashrc

# Install unixODBC development headers
echo ""
echo "[5/5] Installing unixODBC development package..."
sudo apt-get install -y unixodbc-dev

echo ""
echo "=== Installation Complete ==="
echo ""
echo "Installed ODBC drivers:"
odbcinst -q -d

echo ""
echo "Driver name to use in .env file:"
echo "MSSQL_DRIVER=ODBC Driver 18 for SQL Server"
