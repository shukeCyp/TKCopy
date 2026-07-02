import unittest

from tkcopy.utils.frame_matcher import CandidateMatch, choose_temporal_matches


class FrameMatcherTests(unittest.TestCase):
    def test_choose_temporal_matches_prefers_continuous_candidate_when_scores_are_close(self):
        candidates = {
            0: [
                CandidateMatch(0, 100, 1.0, 0, False),
                CandidateMatch(0, 500, 1.1, 0, False),
            ],
            1: [
                CandidateMatch(1, 500, 1.0, 0, False),
                CandidateMatch(1, 101, 2.0, 0, False),
            ],
            2: [
                CandidateMatch(2, 500, 1.0, 0, False),
                CandidateMatch(2, 102, 2.0, 0, False),
            ],
        }

        matches = choose_temporal_matches(candidates)

        self.assertEqual([match.source_frame for match in matches], [100, 101, 102])


if __name__ == "__main__":
    unittest.main()
