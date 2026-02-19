#!/bin/bash

# Force Logout All Users - Clear All Tokens
# This script helps when permission system is updated and users need fresh tokens

echo "🔄 Force Logout All Users"
echo "========================="
echo ""
echo "This will invalidate all existing JWT tokens by:"
echo "1. Updating JWT secret key"
echo "2. Forcing all users to login again"
echo ""
read -p "Are you sure? (yes/no): " confirm

if [ "$confirm" != "yes" ]; then
    echo "❌ Cancelled"
    exit 1
fi

echo ""
echo "📝 Generating new JWT secret..."

# Generate new random secret
NEW_SECRET=$(openssl rand -hex 32)

# Update .env file
cd /var/www/appPatrol-python

if [ -f .env ]; then
    # Backup current .env
    cp .env .env.backup.$(date +%Y%m%d_%H%M%S)
    
    # Update SECRET_KEY
    sed -i "s/^SECRET_KEY=.*/SECRET_KEY=$NEW_SECRET/" .env
    
    echo "✅ JWT secret updated"
    echo "✅ Old .env backed up"
    echo ""
    echo "🔄 Restarting backend..."
    
    pm2 restart patrol-backend
    
    echo ""
    echo "✅ Done! All users must login again."
    echo ""
    echo "📋 What happened:"
    echo "   - New JWT secret generated"
    echo "   - All old tokens are now invalid"
    echo "   - Users will see 401 Unauthorized"
    echo "   - Users must logout and login again"
    echo ""
else
    echo "❌ .env file not found!"
    exit 1
fi
