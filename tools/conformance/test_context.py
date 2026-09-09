"""Wire-level context conformance reference; not a production validator."""
import pathlib
import re
import unittest

from google.protobuf import text_format
from fastverk.product.v1 import context_pb2
from fastverk.product.testing.v1 import fixtures_pb2

# Deliberately explicit: Python str.split(), JavaScript \s, and Swift whitespace
# predicates do not all implement this exact cross-language set.
SEPARATORS = re.compile("[\u0009-\u000d\u0020\u0085\u00a0\u1680\u2000-\u200a\u2028\u2029\u202f\u205f\u3000]+")


def reference_validate(context):
    count = len([word for word in SEPARATORS.split(context.additional_context) if word])
    return context_pb2.ContextValidation(
        context=context,
        word_count=count,
        word_limit=100,
        status=(context_pb2.CONTEXT_VALIDATION_STATUS_ACCEPTED if count <= 100
                else context_pb2.CONTEXT_VALIDATION_STATUS_WORD_LIMIT_EXCEEDED),
    )


class ContextConformance(unittest.TestCase):
    def test_portable_corpus_and_wire_retention(self):
        corpus = fixtures_pb2.ContextFixtures()
        text_format.Parse(pathlib.Path(__file__).with_name("context.textproto").read_text(), corpus)
        self.assertGreaterEqual(len(corpus.cases), 10)
        for case in corpus.cases:
            with self.subTest(case=case.name):
                request = context_pb2.ExecutionContext.FromString(case.input.SerializeToString())
                result = reference_validate(request)
                received = context_pb2.ContextValidation.FromString(result.SerializeToString())
                self.assertEqual(received.word_count, case.expected_word_count)
                self.assertEqual(received.status, case.expected_status)
                self.assertEqual(received.word_limit, 100)
                self.assertEqual(received.context.additional_context, case.input.additional_context)
                self.assertEqual(request, case.input)

    def test_default_does_not_imply_accepted(self):
        self.assertNotEqual(context_pb2.ContextValidation().status,
                            context_pb2.CONTEXT_VALIDATION_STATUS_ACCEPTED)


if __name__ == "__main__":
    unittest.main()
