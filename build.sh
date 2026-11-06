#!/usr/bin/env bash
set -o errexit

python -m pip install --upgrade pip
pip install -r requirements.txt
python manage.py collectstatic --no-input
python manage.py migrate --no-input

products_exist="$(python manage.py shell --verbosity 0 -c 'from marketplace.models import Product; print(Product.objects.exists())')"
if [ "$products_exist" = "False" ]; then
  echo "No products found; loading CRAFTS BAPPY demo catalog."
  python manage.py seed_data
else
  echo "Existing product catalog found; leaving database data unchanged."
fi
