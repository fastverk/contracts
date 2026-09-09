"""Generated-wire compatibility tests; service behavior is tested by consumers."""
import unittest
from fastverk.product.v1 import project_pb2 as p

class ProjectWire(unittest.TestCase):
    def test_optional_outcome_and_uint64_roundtrip(self):
        for outcome in (None, "", "  Research without a repository 😀\n"):
            source = p.ProductProject(project_id="project_1", name="Research", revision=2**64-1)
            if outcome is not None:
                source.outcome = outcome
            for response in (p.CreateProjectResponse(project=source), p.GetProjectResponse(project=source), p.RenameProjectResponse(project=source)):
                decoded = type(response).FromString(response.SerializeToString())
                self.assertEqual(decoded, response)
                self.assertEqual(decoded.project.HasField("outcome"), outcome is not None)
                self.assertEqual(decoded.project.revision, 2**64-1)

    def test_request_values_ignore_wire_order_and_unknown_fields(self):
        # Same known-field request, different field ordering and a future field.
        first = p.CreateProjectRequest.FromString(b"\x0a\x01A\x1a\x01K")
        second = p.CreateProjectRequest.FromString(b"\x1a\x01K\x0a\x01A\x98\x06\x01")
        self.assertNotEqual(first.SerializeToString(), second.SerializeToString())
        def payload(request):
            return (request.name, request.HasField("outcome"), request.outcome)
        self.assertEqual(payload(first), payload(second))
        second.outcome = ""
        self.assertNotEqual(payload(first), payload(second))

    def test_empty_directory_and_cursor_roundtrip(self):
        self.assertEqual(len(p.ListProjectsResponse().projects), 0)
        self.assertEqual(p.ListProjectsResponse().next_page_token, "")
        source = p.ListProjectsResponse(projects=[p.ProductProject(project_id="p1", name="A", revision=1)], next_page_token="opaque")
        self.assertEqual(p.ListProjectsResponse.FromString(source.SerializeToString()), source)

    def test_rename_retry_preserves_expected_revision_and_key(self):
        source = p.RenameProjectRequest(project_id="p1", name="Renamed", expected_revision=2**53+1, idempotency_key="retry_1")
        self.assertEqual(p.RenameProjectRequest.FromString(source.SerializeToString()), source)

    def test_work_admission_retains_context_and_retry_identity(self):
        work = p.ProjectWork(
            project_id="p1",
            run_name="product-p1",
            objective="Restore the build",
            context="Keep the fix small.",
            profile_ref="scoping-measure",
            phase="ADMITTING",
            retry_key="advance_1",
        )
        response = p.AdvanceProjectResponse(work=work)
        self.assertEqual(
            p.AdvanceProjectResponse.FromString(response.SerializeToString()),
            response,
        )
        self.assertEqual(
            p.GetProjectWorkResponse.FromString(
                p.GetProjectWorkResponse(work=work).SerializeToString()
            ).work,
            work,
        )

    def test_unknown_error_code_is_preserved_for_fail_closed_consumer(self):
        error = p.ProjectError(code=99, message="Future failure")
        self.assertEqual(p.ProjectError.FromString(error.SerializeToString()).code, 99)
        self.assertEqual(p.ProjectError().code, p.PROJECT_ERROR_CODE_UNSPECIFIED)

if __name__ == "__main__":
    unittest.main()
