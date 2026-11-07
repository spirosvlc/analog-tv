import pytest
from analog_tv.integrations.feeds import RssNewsProvider

def test_placeholder():
    # Network providers are integration-tested manually; this keeps the module import covered.
    assert RssNewsProvider is not None


def test_emy_region_filter():
    from analog_tv.integrations.feeds import EmyWarningProvider
    assert EmyWarningProvider._matches_region("Warning for Attica and Athens", "Attica")
    assert EmyWarningProvider._matches_region("Προειδοποίηση για Αττική και Αθήνα", "Attica")
    assert not EmyWarningProvider._matches_region("Warning for Crete", "Attica")
