from backend import classifier


def test_complaint_detected():
    result = classifier.classify("This is the worst service, I want a refund immediately, unacceptable!")
    assert result.category == "complaint"
    assert result.urgency in ("medium", "high")
    assert result.source == "rules"


def test_quote_request_detected():
    result = classifier.classify("Hi, how much would it cost to get a quote for a new fence?")
    assert result.category == "quote_request"


def test_scheduling_detected():
    result = classifier.classify("Can I book an appointment for next Tuesday?")
    assert result.category == "scheduling"


def test_faq_detected():
    result = classifier.classify("What are your hours and where is your location?")
    assert result.category == "faq"


def test_spam_detected():
    result = classifier.classify("Click here to win crypto casino prizes, unsubscribe anytime")
    assert result.category == "spam"


def test_empty_text_defaults_to_other_low():
    result = classifier.classify("")
    assert result.category == "other"
    assert result.urgency == "low"


def test_urgent_words_raise_urgency():
    result = classifier.classify("URGENT emergency, water leak in the store right now")
    assert result.urgency in ("medium", "high")


def test_lawyer_complaint_is_high_urgency():
    result = classifier.classify("This is unacceptable, I'm getting my lawyer involved, refund now")
    assert result.category == "complaint"
    assert result.urgency == "high"
