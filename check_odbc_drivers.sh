#!/bin/bash
# Check ODBC drivers on the server

echo "=== Installed ODBC Drivers ==="
odbcinst -q -d

echo ""
echo "=== ODBC Configuration Files ==="
echo "odbcinst.ini location:"
odbcinst -j | grep "DRIVERS"

echo ""
echo "odbc.ini location:"
odbcinst -j | grep "SYSTEM DATA SOURCES"

echo ""
echo "=== Driver Files ==="
if [ -f "/etc/odbcinst.ini" ]; then
    echo "Contents of /etc/odbcinst.ini:"
    cat /etc/odbcinst.ini
else
    echo "/etc/odbcinst.ini not found"
fi
