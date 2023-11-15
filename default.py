from resources.lib.scores import *
import sys

#debug = False
#if len(sys.argv) > 1:
#    # python sucks converting string to boolean, so do this.
#    if sys.argv[1] == 'True':
#        debug = True
#    else:
#        debug = False

scores = Scores(False)
#if debug:
#    scores.service()
#    scores.testGetScores()
#    old_game_stats = copy.copy(scores.new_game_stats[0])
#    scores.new_game_stats[0]['home_score'] = scores.new_game_stats[0]['home_score'] - 1
#    scores.check_if_changed(scores.new_game_stats[0],old_game_stats)
#else:
scores.service()