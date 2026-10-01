import unittest

from music.models import LoopMode, PlaybackState, Track, TrackSource, format_duration


def track(title: str, requester_id: int | None = None) -> Track:
    return Track(
        title=title,
        url=f"https://example.com/{title}",
        source=TrackSource.YOUTUBE,
        requester_id=requester_id,
    )


class PlaybackStateTests(unittest.TestCase):
    def test_track_loop_requeues_current_at_front(self) -> None:
        state = PlaybackState(loop_mode=LoopMode.TRACK)
        first = track("first")
        second = track("second")
        state.enqueue([first, second])

        self.assertEqual(state.claim_next(), first)
        state.finish_current()

        self.assertEqual(tuple(state.queue), (first, second))

    def test_queue_loop_moves_current_to_end(self) -> None:
        state = PlaybackState(loop_mode=LoopMode.QUEUE)
        first = track("first")
        second = track("second")
        state.enqueue([first, second])

        state.claim_next()
        state.finish_current()

        self.assertEqual(tuple(state.queue), (second, first))

    def test_skip_does_not_repeat_track(self) -> None:
        state = PlaybackState(loop_mode=LoopMode.TRACK)
        first = track("first")
        second = track("second")
        state.enqueue([first, second])

        state.claim_next()
        state.finish_current(skipped=True)

        self.assertEqual(tuple(state.queue), (second,))

    def test_invalidate_clears_playback_and_changes_generation(self) -> None:
        state = PlaybackState()
        state.enqueue([track("first"), track("second")])
        state.claim_next()
        generation = state.generation

        state.invalidate(clear_queue=True, reset_loop=True)

        self.assertGreater(state.generation, generation)
        self.assertIsNone(state.current)
        self.assertEqual(tuple(state.queue), ())
        self.assertEqual(state.loop_mode, LoopMode.OFF)

    def test_duration_formatting(self) -> None:
        self.assertEqual(format_duration(65), "1:05")
        self.assertEqual(format_duration(3661), "1:01:01")
        self.assertEqual(format_duration(None), "live/không rõ")

    def test_fair_queue_rotates_requesters_without_reordering_their_tracks(self) -> None:
        state = PlaybackState(fair_queue=True)
        state.enqueue(
            [
                track("a1", 1),
                track("a2", 1),
                track("b1", 2),
                track("b2", 2),
                track("c1", 3),
            ]
        )

        played = []
        while state.queue:
            played.append(state.claim_next().title)
            state.finish_current()

        self.assertEqual(played, ["a1", "b1", "c1", "a2", "b2"])

    def test_priority_tracks_bypass_fair_queue(self) -> None:
        state = PlaybackState(fair_queue=True)
        state.enqueue([track("a1", 1), track("b1", 2)])
        self.assertEqual(state.claim_next().title, "a1")
        state.finish_current()

        state.enqueue_front([track("a-now", 1)])

        self.assertEqual(state.claim_next().title, "a-now")
        self.assertEqual(state.priority_count, 0)

    def test_snapshot_exposes_queue_modes(self) -> None:
        state = PlaybackState(fair_queue=True, autoplay=True)

        snapshot = state.snapshot()

        self.assertTrue(snapshot.fair_queue)
        self.assertTrue(snapshot.autoplay)


if __name__ == "__main__":
    unittest.main()
