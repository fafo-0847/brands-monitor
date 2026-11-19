import unittest

from pipeline import normalize


class NormalizeTests(unittest.TestCase):
    def test_sizes(self):
        cases = {'S': 'S', 'small': 'S', ' Medium ': 'M', 'X-Large': 'XL', '2XL': 'XXL', 'xxxl': '3XL',
                 '11-12 Y': '11-12Y', '6 Months': '6M', '2-3 Years': '2-3Y', '42': '42', '7.5': '7.5',
                 '100ml': '100ml', 'Free Size': 'ONE SIZE', 'PISTAGREEN': None, 'Default': None, '': None,
                 None: None, '2024': None, '0': None}
        for raw, expected in cases.items():
            with self.subTest(raw):
                self.assertEqual(normalize.normalize_size(raw), expected)

    def test_variant_size_uses_the_option_named_size(self):
        options = [{'name': 'Color', 'position': 1, 'values': ['White']},
                   {'name': 'Size', 'position': 2, 'values': ['S', 'M']}]
        self.assertEqual(normalize.variant_size(options, ['White', 'M']), 'M')
        self.assertEqual(normalize.variant_size(options, ['White']), None)

    def test_variant_size_without_a_size_option(self):
        scent = [{'name': 'Scent', 'position': 1, 'values': ['Fresh']}, {'name': 'For', 'position': 2, 'values': ['M']}]
        self.assertIsNone(normalize.variant_size(scent, ['Fresh', 'M']))
        self.assertEqual(normalize.variant_size(None, ['Black', 'XL']), 'XL')
        self.assertIsNone(normalize.variant_size(None, ['Default']))
        self.assertIsNone(normalize.variant_size(None, ['42']))  # a bare number without a Size option is ambiguous

    def test_gender(self):
        self.assertEqual(normalize.gender_of({'type': 'Boys', 'title': '2 Piece Knit Suit', 'tags': ['Men']}), 'kids')
        self.assertEqual(normalize.gender_of({'type': 'Men', 'title': 'Polo'}), 'men')
        self.assertEqual(normalize.gender_of({'tags': ['fragrances-forwomen-perfume'], 'title': 'Pour Femme'}), 'women')
        self.assertIsNone(normalize.gender_of({'tags': ['fragrances-formen', 'fragrances-forwomen']}))
        self.assertEqual(normalize.gender_of({'title': "Women's Embroidered Shirt"}), 'women')
        self.assertIsNone(normalize.gender_of({'title': 'Quilted Suede Gilet'}))

    def test_category(self):
        cases = [({'type': 'Fragrances Division', 'title': '1947'}, 'fragrance-beauty'),
                 ({'type': None, 'title': 'Quilted Suede Gilet'}, 'western'),
                 ({'type': '1 PC', 'title': 'Embellished Dobby Stitched Shirt'}, 'eastern'),
                 ({'type': 'Unstitched', 'title': '3 Piece Lawn Suit'}, 'unstitched'),
                 ({'type': 'Shoes', 'title': 'Black Formal Loafers'}, 'footwear'),
                 ({'type': None, 'title': 'Leather Wallet'}, 'bags-accessories'),
                 ({'type': None, 'title': 'King Bedsheet Set'}, 'home'),
                 ({'type': None, 'title': 'Mystery Item'}, 'other')]
        for item, expected in cases:
            with self.subTest(item['title']):
                self.assertEqual(normalize.category_of(item), expected)
        self.assertTrue({normalize.category_of(item) for item, _ in cases} <= set(normalize.CATEGORIES))

    def test_text_cleaning(self):
        self.assertEqual(normalize.clean_description('<p>A&amp;B</p>  <br> c\x00'), 'A&B c')
        self.assertIsNone(normalize.clean_description('<p> </p>'))
        self.assertEqual(normalize.clean_text('a\x00b'), 'ab')
        self.assertEqual(normalize.clean_images(['//x/a.jpg', None, '', 'https://x/b.jpg']),
                         ['https://x/a.jpg', 'https://x/b.jpg'])


if __name__ == '__main__':
    unittest.main()
