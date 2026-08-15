from oracle.treasury import parse_yield_curve


def test_parse_yield_curve_selects_latest_record():
    xml = """<?xml version='1.0'?>
    <feed xmlns='http://www.w3.org/2005/Atom' xmlns:d='urn:test'>
      <entry><content><d:properties><d:NEW_DATE>2026-08-10T00:00:00</d:NEW_DATE><d:BC_3MONTH>4.01</d:BC_3MONTH></d:properties></content></entry>
      <entry><content><d:properties><d:NEW_DATE>2026-08-11T00:00:00</d:NEW_DATE><d:BC_3MONTH>4.02</d:BC_3MONTH></d:properties></content></entry>
    </feed>"""
    assert parse_yield_curve(xml, "BC_3MONTH") == (__import__("datetime").date(2026, 8, 11), 4.02)
