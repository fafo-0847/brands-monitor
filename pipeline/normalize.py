"""Map each brand's own product type / tags / title onto one shared vocabulary.

Rule-based and deliberately conservative: when nothing matches, the value is None
(gender, size) or 'other' (category) rather than a guess.
"""
import html
import re

# Kept small for the free database (2026-11-19): 3 images, 500 characters of description.
DESCRIPTION_LIMIT = 500
IMAGE_LIMIT = 3

GENDERS = ('women', 'men', 'kids')
CATEGORIES = ('unstitched', 'eastern', 'western', 'formal', 'footwear',
              'bags-accessories', 'fragrance-beauty', 'home', 'other')

_TAG = re.compile(r'<[^>]+>')
_SPACE = re.compile(r'\s+')
_WORD = re.compile(r'[a-z0-9]+')
_UNSTITCHED = re.compile(r'\b(?:un|non)[\s\-_]*stitched\b')
_COORD = re.compile(r'\bco[\s\-_]*ord\b')
# Shopify adds ?v=<timestamp> to image links and changes it often; dropping it stops rows being
# rewritten every scan. private.clean_image_url() in the database must give the same result.
_IMAGE_VERSION = re.compile(r'([?&])v=[0-9]+(?=&|$)&?')
_TRAILING_SEPARATOR = re.compile(r'[?&]$')
_WAISTCOAT = re.compile(r'\bwaist[\s\-_]*coats?\b')
_TRACKSUIT = re.compile(r'\btrack[\s\-_]*suits?\b')

_GENDER_WORDS = {
    'kids': {'kids', 'kid', 'boys', 'boy', 'girls', 'girl', 'infant', 'infants', 'toddler', 'toddlers',
             'baby', 'babies', 'newborn', 'junior', 'juniors', 'teens', 'children', 'child'},
    'women': {'women', 'woman', 'womens', 'ladies', 'lady', 'female', 'femme', 'forwomen', 'her'},
    'men': {'men', 'man', 'mens', 'gents', 'male', 'homme', 'formen', 'him'},
}

# First match wins, so the order is from most to least specific.
_CATEGORY_RULES = (
    ('fragrance-beauty', {'fragrance', 'fragrances', 'perfume', 'perfumes', 'attar', 'cologne', 'deodorant',
                          'makeup', 'lipstick', 'mascara', 'foundation', 'skincare', 'serum', 'cosmetics',
                          'beauty', 'nail', 'bodymist', 'mist'}),
    ('footwear', {'shoe', 'shoes', 'footwear', 'sandal', 'sandals', 'sneaker', 'sneakers', 'heels', 'heel',
                  'pumps', 'slippers', 'slipper', 'chappal', 'chappals', 'khussa', 'khussas', 'loafers', 'loafer',
                  'boots', 'boot', 'bootie', 'booties', 'trainer', 'trainers', 'moccasin', 'moccasins', 'slides', 'peshawari', 'kolhapuri', 'flats', 'joggers'}),
    ('bags-accessories', {'bag', 'bags', 'handbag', 'handbags', 'clutch', 'wallet', 'wallets', 'belt', 'belts',
                          'jewellery', 'jewelry', 'earrings', 'necklace', 'bracelet', 'ring', 'rings', 'watch',
                          'watches', 'sunglasses', 'scarf', 'scarves', 'cap', 'caps', 'socks', 'tie', 'ties',
                          'cufflinks', 'accessories', 'accessory', 'stole', 'stoles', 'hijab', 'backpack',
                          'tote', 'keychain', 'perfumebox', 'gloves', 'glove', 'beanie', 'beanies'}),
    ('unstitched', {'unstitched', 'fabric', 'fabrics'}),
    ('formal', {'formal', 'formals', 'bridal', 'bridals', 'luxury', 'wedding', 'sherwani', 'lehenga', 'lehnga',
                'gharara', 'sharara', 'festive', 'couture', 'chiffon', 'tuxedo', 'suiting'}),
    ('western', {'western', 'jeans', 'denim', 'tee', 'tees', 'tshirt', 'tshirts', 'polo', 'polos', 'hoodie',
                 'hoodies', 'sweatshirt', 'sweatshirts', 'jacket', 'jackets', 'blazer', 'blazers', 'chino',
                 'chinos', 'shorts', 'trouser', 'trousers', 'pants', 'sweater', 'sweaters', 'cardigan',
                 'dress', 'dresses', 'skirt', 'skirts', 'top', 'tops', 'blouse', 'jumpsuit', 'activewear',
                 'tracksuit', 'gilet', 'coat', 'coats', 'pullover', 'cargo', 'jogger', 'leggings',
                 'pant', 'tights', 'vest', 'vests', 'coord', 'sweatpant', 'sweatpants', 'trousers',
                 'jersey', 'jerseys', 'dungaree', 'dungarees'}),
    ('eastern', {'kurta', 'kurtas', 'shalwar', 'kameez', 'qameez', 'waistcoat', 'waistcoats', 'kurti', 'kurtis',
                 'pret', 'stitched', 'dupatta', 'shawl', 'shawls', 'kaftan', 'abaya', 'abayas', 'pishwas',
                 'angrakha', 'frock', 'frocks', 'pc', 'piece', 'pcs', 'suit', 'suits', 'eastern', 'ethnic',
                 'lawn', 'khaddar', 'karandi', 'cambric', 'kameezshalwar'}),
    ('home', {'bedding', 'towel', 'towels', 'bedspread', 'tablecloth', 'cushion', 'cushions', 'bedsheet', 'bedsheets', 'curtain', 'curtains',
              'comforter', 'duvet', 'quilt', 'rug', 'rugs', 'tableware', 'homeware', 'pillow', 'blanket',
              'mattress', 'mug', 'mugs', 'candle', 'candles'}),

)

# Used only when no rule above matches at any level, so a brand's own "formal" tag still wins
# over the bare word "shirt" in a product type.
_FALLBACK_RULES = (
    ('western', {'shirt', 'shirts', 'short'}),
)

_ALPHA_SIZES = {
    'xxs': 'XXS', '2xs': 'XXS', 'xs': 'XS', 'xsmall': 'XS', 's': 'S', 'small': 'S', 'm': 'M', 'medium': 'M',
    'l': 'L', 'large': 'L', 'xl': 'XL', 'xlarge': 'XL', 'xxl': 'XXL', '2xl': 'XXL', 'xxxl': '3XL',
    '3xl': '3XL', '4xl': '4XL', 'xxxxl': '4XL', '5xl': '5XL', 'os': 'ONE SIZE', 'onesize': 'ONE SIZE',
    'freesize': 'ONE SIZE', 'free': 'ONE SIZE', 'standard': 'ONE SIZE',
}
_AGE = re.compile(r'^(\d{1,2})(?:\s*-\s*(\d{1,2}))?\s*(y|yr|yrs|year|years|m|mo|month|months)$', re.I)
_NUMBER = re.compile(r'^(\d{1,3})(?:\.(5|0))?$')
_VOLUME = re.compile(r'^(\d{1,4})\s*(ml|g|gm|kg|l|oz)$', re.I)


def clean_text(value):
    """Plain text without NUL bytes (Postgres text cannot hold them)."""
    if value is None:
        return None
    return str(value).replace('\x00', '')


def clean_description(value):
    if not value:
        return None
    text = html.unescape(_TAG.sub(' ', str(value))).replace('\x00', '')
    text = _SPACE.sub(' ', text).strip()
    return text[:DESCRIPTION_LIMIT] or None


def clean_image_url(url):
    """Drop the ?v= cache-busting parameter, keeping any other parameters."""
    return _TRAILING_SEPARATOR.sub('', _IMAGE_VERSION.sub(r'\1', url))


def clean_images(images):
    result = []
    for image in images or []:
        if not isinstance(image, str) or not image:
            continue
        if image.startswith('//'):
            image = 'https:' + image
        result.append(clean_image_url(image.replace('\x00', '')))
        if len(result) == IMAGE_LIMIT:
            break
    return result


def _words(*parts):
    found = set()
    for part in parts:
        if not part:
            continue
        values = part if isinstance(part, (list, tuple)) else [part]
        for value in values:
            lowered = str(value).lower().replace('t-shirt', 'tshirt').replace('for women', 'forwomen') \
                .replace('for men', 'formen')
            lowered = _UNSTITCHED.sub('unstitched', lowered)
            lowered = _COORD.sub('coord', lowered)
            lowered = _WAISTCOAT.sub('waistcoat', lowered)
            lowered = _TRACKSUIT.sub('tracksuit', lowered)
            found.update(_WORD.findall(lowered))
    return found


def gender_of(product):
    """'women', 'men', 'kids' or None. Type and tags outrank the title."""
    strong = _words(product.get('type'), product.get('tags'), product.get('vendor'))
    weak = _words(product.get('title'), product.get('handle'))
    for words in (strong, weak):
        hits = [gender for gender in ('kids', 'women', 'men') if words & _GENDER_WORDS[gender]]
        if 'kids' in hits:
            return 'kids'
        if len(hits) == 1:
            return hits[0]
        if len(hits) > 1:
            return None  # tagged for both (unisex or a mixed collection tag)
    return None


def category_of(product, rules=None):
    """Shared category. `rules` is the brand's entry in pipeline/brand_types.json, if any:
    an exact match on the brand's own product type wins, then the keyword rules; for a brand
    with a `primary` category, 'formal' and 'other' become that category."""
    rules = rules or {}
    mapped = (rules.get('types') or {}).get((product.get('type') or '').strip())
    if mapped:
        return mapped
    category = _keyword_category(product)
    if rules.get('primary') and category in ('formal', 'other'):
        return rules['primary']
    return category


def _keyword_category(product):
    strong = _words(product.get('type'))
    medium = _words(product.get('title'))
    weak = _words(product.get('tags'), product.get('handle'))
    for rules in (_CATEGORY_RULES, _FALLBACK_RULES):
        for words in (strong, medium, weak):
            for category, keywords in rules:
                if words & keywords:
                    return category
    return 'other'


def normalize_size(value):
    """Canonical size label for one option value, or None when it is not a size."""
    if value is None:
        return None
    text = str(value).strip()
    if not text or len(text) > 24:
        return None
    key = re.sub(r'[\s\-_/.]', '', text.lower())
    if key in _ALPHA_SIZES:
        return _ALPHA_SIZES[key]
    age = _AGE.match(text)
    if age:
        unit = 'Y' if age.group(3).lower().startswith('y') else 'M'
        span = age.group(1) if not age.group(2) else f'{age.group(1)}-{age.group(2)}'
        return f'{span}{unit}'
    number = _NUMBER.match(text)
    if number:
        whole = int(number.group(1))
        if 0 < whole <= 60:
            return f'{whole}.5' if number.group(2) == '5' else str(whole)
        return None
    volume = _VOLUME.match(text)
    if volume:
        return f'{int(volume.group(1))}{volume.group(2).lower()}'
    return None


def size_position(product_options):
    """Index of the option named like 'Size' in Shopify-style option metadata, or None."""
    if not isinstance(product_options, list):
        return None
    for index, option in enumerate(product_options):
        if isinstance(option, dict) and 'size' in str(option.get('name', '')).lower():
            return index
    return None


def variant_size(product_options, variant_options):
    values = [value for value in (variant_options or []) if value is not None]
    position = size_position(product_options)
    if position is not None:
        return normalize_size(values[position]) if position < len(values) else None
    named = isinstance(product_options, list) and any(isinstance(o, dict) and o.get('name') for o in product_options)
    if named:
        return None  # the brand names its options and none of them is a size
    for value in values:
        size = normalize_size(value)
        if size and not _NUMBER.match(str(value).strip()):
            return size
    return None
