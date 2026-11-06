#!/usr/bin/env bash
set -o errexit

python -m pip install --upgrade pip
pip install -r requirements.txt
python manage.py collectstatic --no-input
python manage.py migrate --no-input

if [ "$(python manage.py shell -c 'from marketplace.models import Product; print(Product.objects.exists())')" = "False" ]; then
  python manage.py seed_data
fi
