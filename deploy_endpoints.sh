#!/bin/bash
# Deploy endpoints.yaml to server

echo "=== Deploying endpoints.yaml to server ==="
echo ""

# Use scp to copy the file
scp src/config/endpoints.yaml administrator@mstrws:~/venus/src/config/endpoints.yaml

if [ $? -eq 0 ]; then
    echo ""
    echo "✅ endpoints.yaml deployed successfully!"
    echo ""
    echo "Now restart gunicorn on the server:"
    echo "  cd ~/venus && ./quick_update.sh"
else
    echo ""
    echo "❌ Failed to deploy endpoints.yaml"
    echo "You may need to copy it manually"
fi
