import copy
import os
import pytz
import requests
import time
import datetime
import xbmc
import xbmcaddon
import xbmcgui
import xbmcvfs

#There is a mix of using global vars and not
#incosinsitant use of true/false
#Will wantg to put all messages into a dictionary.. and purge at end of day.
#show all messgaes for scores
#haven't verified this runs for multiple days, but code looks like it doea
#change stats objects from arrays to dictionaries and key access them for comparision

# from the  end of games, it will loop and check ever time until 3 in the morning
# It then gets the schedule and sleeps until game time.
#Issue 1
# sometimes it doesn't wake up from sleep, so I put in max sleep time.

#TODO: still need to determine if boxscore and score are updated at same time.
# eventually pass 'strength' to getlastGoal and add it in desc return and replace score description. 
# try threads and put in a minute after to ut a second message with the assist?
#https://www.geeksforgeeks.org/how-to-create-a-new-thread-in-python/

#Potential Issues:
# if it is not noted that all games are finished, then it will run all the next day and not sleep.
# --> not sure if this is something or an issue based on a bug.
# What happens after midnight.  I'd get games for next day.
# I could use /now while active, but use /date when trying to restart

def is_between(now, start, end):
    is_between = False

    is_between |= start <= now <= end
    is_between |= end < start and (start <= now or now <= end)

    return is_between


class Scores:

    def __init__(self, debugflg):
        self.addon = xbmcaddon.Addon()
        self.addon_path = xbmcvfs.translatePath(self.addon.getAddonInfo('path'))
        self.local_string = self.addon.getLocalizedString
        self.ua_ipad = 'Mozilla/5.0 (iPad; CPU OS 8_4 like Mac OS X) AppleWebKit/600.1.4 (KHTML, like Gecko) Mobile/12H143 ipad nhl 5.0925'
        self.nhl_logo = os.path.join(self.addon_path,'resources','nhl_logo.png')
        self.logo = {};
        self.logo['ARI']  = os.path.join(self.addon_path,'resources','ARI.png')
        self.logo['ANA']  = os.path.join(self.addon_path,'resources','ANA.png')
        self.logo['BOS']  = os.path.join(self.addon_path,'resources','BOS.png')
        self.logo['BUF']  = os.path.join(self.addon_path,'resources','BUF.png')
        self.logo['CAR']  = os.path.join(self.addon_path,'resources','CAR.png')
        self.logo['CGY']  = os.path.join(self.addon_path,'resources','CGY.png')
        self.logo['CBJ']  = os.path.join(self.addon_path,'resources','CBJ.png')
        self.logo['CHI']  = os.path.join(self.addon_path,'resources','CHI.png')
        self.logo['COL']  = os.path.join(self.addon_path,'resources','COL.png')
        self.logo['DAL']  = os.path.join(self.addon_path,'resources','DAL.png')
        self.logo['DET']  = os.path.join(self.addon_path,'resources','DET.png')
        self.logo['EDM']  = os.path.join(self.addon_path,'resources','EDM.png')
        self.logo['FLA']  = os.path.join(self.addon_path,'resources','FLA.png')
        self.logo['LAK']  = os.path.join(self.addon_path,'resources','LAK.png')
        self.logo['MIN']  = os.path.join(self.addon_path,'resources','MIN.png')
        self.logo['MTL']  = os.path.join(self.addon_path,'resources','MTL.png')
        self.logo['NSH']  = os.path.join(self.addon_path,'resources','NSH.png')
        self.logo['NJD']  = os.path.join(self.addon_path,'resources','NJD.png')
        self.logo['NYI']  = os.path.join(self.addon_path,'resources','NYI.png')
        self.logo['NYR']  = os.path.join(self.addon_path,'resources','NYR.png')
        self.logo['OTT']  = os.path.join(self.addon_path,'resources','OTT.png')
        self.logo['PIT']  = os.path.join(self.addon_path,'resources','PIT.png')
        self.logo['PHI']  = os.path.join(self.addon_path,'resources','PHI.png')
        self.logo['SEA']  = os.path.join(self.addon_path,'resources','SEA.png')
        self.logo['SJS']  = os.path.join(self.addon_path,'resources','SJS.png')
        self.logo['STL']  = os.path.join(self.addon_path,'resources','STL.png')
        self.logo['TBL']  = os.path.join(self.addon_path,'resources','TBL.png')
        self.logo['TOR']  = os.path.join(self.addon_path,'resources','TOR.png')
        self.logo['VAN']  = os.path.join(self.addon_path,'resources','VAN.png')
        self.logo['WPG']  = os.path.join(self.addon_path,'resources','WPG.png')
        self.logo['WSH']  = os.path.join(self.addon_path,'resources','WSH.png')
        self.logo['VGK']  = os.path.join(self.addon_path,'resources','VGK.png')
        self.api_url = 'https://api-web.nhle.com/v1/score/%s'
        self.api_boxscore_url = 'https://api-web.nhle.com/v1/gamecenter/%s/landing'
        self.headshot_url = 'http://nhl.bamcontent.com/images/headshots/current/60x60/%s@2x.png'
        #aee colors.xml in kodi app
        self.score_color = 'FF90EE90'    #lightgreen
        self.score_color_other_team = 'FFFFFAF0'  #floralwhite
        self.gametime_color = 'FFFFFF00'  #yellow
        self.new_game_stats = []
        self.wait = 30
        self.init_wait = 0
        self.display_seconds = 5
        self.display_milliseconds = self.display_seconds * 1000
        self.delay_seconds = 1
        self.delayy_milliseconds = self.delay_seconds * 1000
        self.dialog = xbmcgui.Dialog()
        self.monitor = xbmc.Monitor()
        self.test = debugflg
        # WHhy is this 25 minutes, Do I need it
        self.DAILY_CHECK_TIMER_PERIOD = 1500 #25 minutes
        self.MAX_SLEEP_TIME = 10800 #3 h0urs
        self.loglevel = xbmc.LOGINFO
        self.all_messages = {}
        self.last_json = {}

     


    def service(self):
        first_run = True
        self.addon.setSetting(id='score_updates', value='false')

      
        #see if I can wrap this for bdebug purposes. this is different than wait
        #while not self.monitor.abortRequested():
        ##-while 1:
        while not self.monitor_abortRequested():
            if self.monitor_waitForAbort(1):
                self.logger(f"abort requested was seen")
                break
            
            # waiting every 25 minutes, then if time is between 3 and 4 AM, turn on processing I guess looking to ensure games wchedule is up to date
            #daily_check_time = is_between(datetime.datetime.now().time(), datetime.time(3), datetime.time(4))
            daily_check_time = datetime.datetime.now().time() > datetime.time(3)
            self.logger("loop execution")
            ##running = self.addon.getSettingBool(id='score_updates')
            msg = f"first_run: {first_run}, daily_check_time: {daily_check_time}, running: {self.scoring_updates_on()}"       
            self.logger(msg)

            # on startup, or ar 3/4 AM, or after max sleep check to see if we should start
            if first_run or (daily_check_time and not self.scoring_updates_on()):
                self.logger("time to check. Turn service on")
                
                sleep_seconds = self.check_games_scheduled() #check for games, sleep until games start
                self.logger(f"seconds before 1st game: {sleep_seconds}")
                # thi will always be 25 minlate, for 1st interation.  self.DAILY_CHECK_TIMER_PERIOD
                if sleep_seconds < self.DAILY_CHECK_TIMER_PERIOD:
                    self.toggle_service_on()
                    self.notify(self.local_string(30300), self.local_string(30350))
                    #In above, if waiting, this still executes (probably because in debug, the libs work differently)
                    self.logger(f"running: {self.scoring_updates_on()}")

                    if self.monitor_abortRequested():
                        self.logger(f"abort requested was seen")
                        
                    #SML: this stays in scoring_updates until the games are over.
                    self.scoring_updates()

                    # this should be redundant
                    self.toggle_service_off()

                first_run = False


            if (self.test):
                break;
            self.logger(f"sleep for: {self.MAX_SLEEP_TIME}")
            self.monitor_waitForAbort(self.MAX_SLEEP_TIME)

    def testGetScores(self):
        json = self.get_scoreboard()
        self.new_game_stats.clear()
        self.logger("Games: " + str(len(json['games'])))
        for game in json['games']:
            self.get_new_stats(game)

            
    ###########################################################
    # this is called from a forever loop looking for updates
    # I don't think any of break statements within the loop do anything
    ###########################################################
    def scoring_updates(self):
        first_time_thru = True
        old_game_stats = []
        while self.scoring_updates_on() and not self.monitor_abortRequested():
        ##-if self.scoring_updates_on():
            json = self.get_scoreboard()
            self.new_game_stats.clear()
            self.logger("Games: " + str(len(json['games'])))
            for game in json['games']:
                # Break out of loop if updates disabled
                if not self.scoring_updates_on(): break
                self.get_new_stats(game)

            if not first_time_thru:
                #set these always, so user can change config and have it recognized
                self.set_display_time()
                self.set_delay_time()
                #assume all games finished
                all_games_finished = True
                self.logger("new game stats count: " + str(len(self.new_game_stats)))
                self.logger("old game stats count: " + str(len(old_game_stats)))
                if len(old_game_stats) == 0 or len(self.new_game_stats) == 0:
                    all_games_finished = False
                    
                for new_item in self.new_game_stats:
                    if not self.scoring_updates_on(): break
                    # Check if all games have finished
                    if new_item['gameState'] in ['LIVE','CRIT']: all_games_finished = False
                    #if 'final' not in new_item['gameState'].lower(): all_games_finished = False
                    for old_item in old_game_stats:
                        if not self.scoring_updates_on(): break
                        if new_item['game_id'] == old_item['game_id']:
                            self.check_if_changed(new_item, old_item)

                #if self.test:
                #    self.testing(new_item)

                # if all games have finished for the night stop the script
                if all_games_finished and self.scoring_updates_on():
                    self.toggle_service_off()
                    self.logger("End of day")
                    self.all_messages.clear()
                    # If the user is watching a game don't display the all games finished message
                    #if 'nhl_game_video' not in self.get_video_playing():
                    #    self.notify(self.local_string(30300), self.local_string(30360), self.nhl_logo)

            old_game_stats.clear()
            old_game_stats = copy.deepcopy(self.new_game_stats)
            ##- in debug, only don't allow the service to loop.
            if self.test and first_time_thru == True:
                break;
            first_time_thru = False
            # If kodi exits or goes idle stop running the script
            if self.monitor_waitForAbort(self.wait):
                self.logger("**************Abort Called**********************")
                ##- comment this out.
                break
                
                
    ###########################################################
    def get_new_stats(self, game):
    ###########################################################
        #video_playing = self.get_video_playing()  
        #self.logger(f"Video Playing: {video_playing}")
        ateam = game['awayTeam']['abbrev']
        hteam = game['homeTeam']['abbrev']
        logo = ""
        current_period = 0
        game_clock = ""
        if game['gameState']  not in ['FUT','PRE']:
            current_period = game['period']
        desc = ''
        headshot = ''
        if 'period' in game:
            periodStr =  self.get_period(game['period'] )
        if 'clock' in game:
            game_clock = f"{game['clock']['timeRemaining']} {periodStr}"
            if game['clock']['inIntermission'] == True:
                game_clock = f"00:00 {periodStr}"
            
        try:
            goal = game['goals'][-1]
            desc = goal['name']['default'] + " (" + str(goal['goalsToDate']) + ")"
            strength = goal['strength'] if goal['strength'] != "EV" else "Even"
            desc = f"({strength}) {desc}"
            if goal['teamAbbrev'] == ateam:
                logo = self.logo[ateam]
            else:
                logo = self.logo[hteam]
            # Remove Assists if there are none
            #--if ', assists: none' in desc: desc = desc[:desc.find(', assists: none')]
            #player_id = game['scoringPlays'][-1]['players'][0]['player']['link']
            #player_id = player_id[player_id.rfind('/') + 1:]
            #headshot = self.headshot_url % player_id
            headshot = goal['mugshot']
            #--game_clock = goal['timeInPeriod']
        except:
            pass

        #-if 'in progress' in game_clock.lower():
        #-    game_clock = f"{game['linescore']['currentPeriodTimeRemaining']} {game['linescore']['currentPeriodOrdinal']}"

        # Disable spoiler by not showing score notifications for the game the user is currently watching
        #SML. I took this out
        #if ateam.lower() not in video_playing and hteam.lower() not in video_playing:
            # Sometimes goal desc are generic, don't alert until more info has been added to the feed
        #if self.getSetting(id="goal_desc") != 'true' or desc.lower() != 'goal':
        if self.getSetting(id="goal_desc") == 'true':
            awayScore = 0
            if 'score' in game['awayTeam']:
                awayScore = game['awayTeam']['score']
            homeScore = 0
            if 'score' in game['homeTeam']:
                homeScore = game['homeTeam']['score']

            self.new_game_stats.append(
                {"game_id": game['id'],
                "away_name": game['awayTeam']['abbrev'],
                "home_name": game['homeTeam']['abbrev'],
                "away_score": awayScore,
                "home_score": homeScore,
                "game_clock": game_clock,
                "period": current_period,
                "goal_desc": desc,
                "headshot": headshot,
                "logo" : logo,
                "gameState": game['gameState']})

    ###########################################################
    def check_if_changed(self, new_item, old_item):
    ###########################################################
        title = None
        message = None
        img = self.nhl_logo
        self.logger("~"+str(old_item))
        self.logger("-"+str(new_item))
 
        if 'final' in new_item['gameState'].lower() and 'final' not in old_item['gameState'].lower():
            title, message, img = self.final_score_message(new_item)
        elif 'live' in new_item['gameState'].lower() and 'live' not in old_item['gameState'].lower():
            title, message = self.game_started_message(new_item)
        elif new_item['period'] != old_item['period'] and 'live' in new_item['gameState'].lower():
            # Notify user that the game has started / period has changed
            title, message = self.period_change_message(new_item)
        elif new_item['game_clock'][:5] == "00:00" and old_item['game_clock'][:5] != "00:00" :
            # Notify user that the periord has ended
            title, message = self.period_ended_message(new_item)
            
        #TODO: maybe ignore this and check goals by all_messages
        # forget score change and just use desc change.  The desc includes goal number, so if a player score two in a row
        # the desc changes.  This also catches case where score is updated 1st, then the goal scorer is added and found
        # int the next api call.
             # Highlight score for the team that just scored a goal
            # 2 delays possible: 
            # goal is noted in score, but person scoring is not updated yet.
            # goal isn't recorded in landing paging for game where we go for assits
            # --> so getting last goal can be a little risky
            # wait 30 seconds for score to update fully.
            #       
        #elif (new_item['home_score'] != old_item['home_score'] and new_item['home_score'] > 0) or \
        #     (new_item['away_score'] != old_item['away_score'] and new_item['away_score'] > 0):
        elif new_item['goal_desc'] != old_item['goal_desc']:
            

            self.monitor_waitForAbort(30)
            goal_number = new_item['home_score'] + new_item['away_score'] 
            last_score = self.get_last_goal(new_item['game_id'], goal_number)

            title, message = self.goal_scored_message(new_item, old_item, last_score)

            # Get goal scorers headshot if notification is a score update -> changed to team logo
            #Note can't use SVG found in API (not supported in KODI), so reference PNGs built into app
            if new_item['logo'] != "":
                img = new_item['logo']

        if title is not None and message is not None:
            self.notify(title, message, img)
            self.monitor_waitForAbort(self.display_seconds + 5)

    ###########################################################
    def get_period(self, period):
    ###########################################################
        periodStr = "OT"
        if period == 1:
            periodStr = "1st"
        if period== 2:
            periodStr = "2nd"
        if period == 3:
            periodStr = "3rd"
        return periodStr
    
    ###########################################################
    def check_games_scheduled(self):
    ###########################################################
        # Check if any games are scheduled for today.
        # If so, check if any are live and if not sleep until first game starts
        
        sleep_seconds = 0
        seconds_to_start = 1500
        json = self.get_scoreboard()
        if 'games' not in json:
            self.toggle_service_off()
            self.notify(self.local_string(30300), self.local_string(30352))
            #SML: I should sleep here..
        else:
            live_games = False
            for game in json['games']:
                if game['gameState']  in ['LIVE','CRIT','PRE']:
                    live_games = True
                    seconds_to_start = 0
                    break

            if len(json['games']) == 0:
                #put in a no games message?
                self.notify("WTF Betman", "No Games Today", self.nhl_logo)
                return 86400
                #SML: I should sleep here..
            game = json['games'][0]
            if not live_games:
                # date found in stream is UTC
                first_game_start = self.string_to_date(game['startTimeUTC'], "%Y-%m-%dT%H:%M:%SZ")
                # if debuging and using an old date, this will mean starting right away and not sleeping
                seconds_to_start = int((first_game_start - datetime.datetime.utcnow()).total_seconds())
                if seconds_to_start  >= 6600:
                    # hour and 50 minutes or more just display hours
                    delay_time = f" {round(seconds_to_start  / 3600)} hours"
                elif seconds_to_start  >= 4200:
                    # hour and 10 minutes
                    delay_time = f"an hour and {round((seconds_to_start  / 60) - 60)} minutes"
                elif seconds_to_start  >= 3000:
                    # 50 minutes
                    delay_time = "an hour"
                else:
                    delay_time = f"{round((seconds_to_start  / 60))} minutes"
                    
                #check for max sleep time as sometimes too long is forgotten?? 
                sleep_seconds =  seconds_to_start          
                if seconds_to_start  > self.MAX_SLEEP_TIME:
                    sleep_seconds = self.MAX_SLEEP_TIME
                    
                if sleep_seconds > 0: 
                    self.logger(f"sleeping {sleep_seconds} seconds")
                    message = f"First game starts in about {delay_time}"
                    self.notify(self.local_string(30300), message)
                    self.monitor_waitForAbort(sleep_seconds)

        return seconds_to_start - sleep_seconds
                    
    #put in try actually hit an issue with nhl.com once
    ###########################################################            
    def get_scoreboard(self):
    ###########################################################       
    # /now doesn't update to current date until later in the new date, so use a date specifically     
        if self.test:
            url = self.api_url % "2023-11-14"
        else:
            #url = self.api_url % self.local_to_pacific()
            url = self.api_url % datetime.datetime.now().strftime('%Y-%m-%d')
        #self.logger(f"{url}")
        try:    
            headers = {'User-Agent': self.ua_ipad}
            r = requests.get(url, headers=headers)
            self.last_json = r.json()
            self.logger(self.last_json)
        except:
            pass
        return self.last_json
    
    ###########################################################            
    def get_last_goal(self, game_id, goal_number):
    ###########################################################     
    # could look for x goal. if not found, sleep for 10 seconds than retry again until found.
    # Q: Do all periods show up in landing while the game is live. I suspect not and the periods occur when 
    # game is in that state
        self.logger(f"looking for goal: {goal_number}")
        resp = ""       
        if self.test:
            url = self.api_boxscore_url % '2023020229'
        else:
            #url = self.api_url % self.local_to_pacific()
            url = self.api_boxscore_url % game_id
            
        try:    
            headers = {'User-Agent': self.ua_ipad}
            r = requests.get(url, headers=headers)
            last_json = r.json()
            goal = ""
            
            lastGoalPeriodArrIdx = len(last_json['summary']['scoring']) -1
            totalReportedGoals = 0
            if (lastGoalPeriodArrIdx == 3):
                totalReportedGoals += len(last_json['summary']['scoring'][3]['goals'])
            if (lastGoalPeriodArrIdx >= 2):
                totalReportedGoals += len(last_json['summary']['scoring'][2]['goals'])                
            if (lastGoalPeriodArrIdx >= 1):
                totalReportedGoals += len(last_json['summary']['scoring'][1]['goals'])  
            if (lastGoalPeriodArrIdx >= 0):
                totalReportedGoals += len(last_json['summary']['scoring'][0]['goals'])      

            if (totalReportedGoals < goal_number):
                resp = "...goal not reported yet..."            
            elif lastGoalPeriodArrIdx > -1:
                if len(last_json['summary']['scoring'][lastGoalPeriodArrIdx]) > 0:
                    goal = last_json['summary']['scoring'][lastGoalPeriodArrIdx]['goals'][-1]
                    resp = "(" + goal['strength'] + ") " + goal['firstName']['default'] + " " + goal['lastName']['default'] + " (" + str(goal['goalsToDate']) + ") "
                    if len(goal['assists']) > 0:
                        resp += "from "  +  goal['assists'][0]['firstName']['default'] + " " + goal['assists'][0]['lastName']['default'] + " (" + str(goal['assists'][0]['assistsToDate']) + ") "
                    if len(goal['assists']) > 1:
                        resp += ", "  +  goal['assists'][1]['firstName']['default'] + " " + goal['assists'][1]['lastName']['default'] + " (" + str(goal['assists'][1]['assistsToDate']) + ") "
            

        except:
            pass
        return resp
                
    ###########################################################            
    ###########################################################            
    def scoring_updates_on(self):
        return self.getSetting(id="score_updates") == 'true'

    def toggle_service_on(self):
        self.logger(f"Toggle Service ON")
        self.addon.setSetting(id='score_updates', value='true')
        return

    def toggle_service_off(self):
        self.logger(f"Toggle Service OFF")
        self.addon.setSetting(id='score_updates', value='false')
        return


    def local_to_pacific(self):
        pacific = pytz.timezone('US/Pacific')
        local_to_utc = datetime.datetime.now(pytz.timezone('UTC'))
        local_to_pacific = local_to_utc.astimezone(pacific).strftime('%Y-%m-%d')
        return local_to_pacific

    def string_to_date(self, string, date_format):
        try:
            date = datetime.datetime.strptime(str(string), date_format)
        except TypeError:
            date = datetime.datetime(*(time.strptime(str(string), date_format)[0:6]))

        return date





    def get_video_playing(self):
        video_playing = ''
        if xbmc.Player().isPlayingVideo(): video_playing = xbmc.Player().getPlayingFile().lower()
        return video_playing


    def set_display_time(self):
        self.display_seconds = int(self.getSetting(id="display_seconds"))
        self.display_milliseconds = self.display_seconds * 1000

    def set_delay_time(self):
        self.delay_seconds = int(self.getSetting(id="delay_seconds"))
        self.delaymilliseconds = self.delay_seconds * 1000
        
    ###########################################################        
    def final_score_message(self, new_item):
        # Highlight score of the winning team
        title = self.local_string(30355)
        img = ""
        if new_item['away_score'] > new_item['home_score']:
            away_score = f"[COLOR={self.score_color}]{new_item['away_name']} {new_item['away_score']}[/COLOR]"
            home_score = f"{new_item['home_name']} {new_item['home_score']}"
            img = self.logo[new_item['away_name']]
        else:
            away_score = f"{new_item['away_name']} {new_item['away_score']}"
            home_score = f"[COLOR={self.score_color}]{new_item['home_name']} {new_item['home_score']}[/COLOR]"
            img = self.logo[new_item['home_name']]
    
        game_clock = f"[COLOR={self.gametime_color}]{new_item['game_clock']}[/COLOR]"
        message = f"{away_score}    {home_score}"
        return title, message, img

    def game_started_message(self, new_item):
        title = self.local_string(30358)
        message = f"{new_item['away_name']} vs {new_item['home_name']}"
        return title, message

    def period_change_message(self, new_item):
        # Notify user that the game has started / period has changed
        title = self.local_string(30370)
        periodStr =  self.get_period(new_item['period'] )
        message = f"{new_item['away_name']} {new_item['away_score']}    " \
                  f"{new_item['home_name']} {new_item['home_score']}   " \
                  f"[COLOR={self.gametime_color}]{periodStr} has started[/COLOR]"

        return title, message

    def period_ended_message(self, new_item):
        # Notify user that the game has started / period has changed
        title = self.local_string(30370)
        msg = new_item['game_clock'].replace("00:00","End of")
        message = f"{new_item['away_name']} {new_item['away_score']}    " \
                  f"{new_item['home_name']} {new_item['home_score']}   " \
                  f"[COLOR={self.gametime_color}]{msg} [/COLOR]"

        return title, message

    def goal_scored_message(self, new_item, old_item, last_score):
        #game clock already has periodStr in it
        #periodStr =  self.get_period(new_item['period'] )
        # Highlight score for the team that just scored a goal
        away_score = f"[COLOR={self.score_color_other_team}]{new_item['away_name']} {new_item['away_score']}[/COLOR]"
        home_score = f"[COLOR={self.score_color_other_team}]{new_item['home_name']} {new_item['home_score']}[/COLOR]"
        game_clock = f"[COLOR={self.gametime_color}]{new_item['game_clock']}[/COLOR]"
        
        if new_item['away_score'] != old_item['away_score']:
            away_score = f"[COLOR={self.score_color}]{new_item['away_name']} {new_item['away_score']}[/COLOR]"
        if new_item['home_score'] != old_item['home_score']:
            home_score = f"[COLOR={self.score_color}]{new_item['home_name']} {new_item['home_score']}[/COLOR]"

        if self.getSetting(id="goal_desc") == 'false':
            title = self.local_string(30365)
            message = f"{away_score}    {home_score}    {game_clock}"
        else:
            title = f"{away_score}    {home_score}    {game_clock}"
            #message = new_item['goal_desc']
            # temporay to see of there is a big time delay in updating landing.
            # we are now waiting, so ignore anythig from scoreboard (ie. new_item stuff) 
            #message = new_item['goal_desc'] + " " + last_score
            message = last_score

        return title, message



    def testing(self, new_item):
            img = self.nhl_logo

            title, message = self.final_score_message(new_item)
            self.notify(title, message, img)
            self.monitor_waitForAbort(self.display_seconds + 5)

            title, message = self.game_started_message(new_item)
            self.notify(title, message, img)
            self.monitor_waitForAbort(self.display_seconds + 5)

            title, message = self.period_change_message(new_item)
            self.notify(title, message, img)
            self.monitor_waitForAbort(self.display_seconds + 5)

            title, message = self.goal_scored_message(new_item, new_item)
            # Get goal scorers headshot if notification is a score update
            if self.getSetting(id="goal_desc") == 'true' and new_item['headshot'] != '': img = new_item['headshot']
            self.notify(title, message, img)
            self.monitor_waitForAbort(self.display_seconds + 5)
            
    ###########################################################  
    # Modules to use for debuggiung
    ###########################################################      
    def getSetting(self, id):
        val = self.addon.getSetting(id=f"{id}")
        if val == "" and id in "display_seconds":
           return "5"
        if val == "" and id in "delay_seconds":
           return "5"
        if val == "" and id in "score_updates":
           return "true"
        if val == "" and id in "goal_desc":
           return "true"
       
        return val

    def monitor_waitForAbort(self, seconds):
        if (self.test):
            #xbmc.log(f"[script.nhlscores] self test", self.loglevel)
            time.sleep(seconds)
            return
        else:
            #xbmc.log(f"[script.nhlscores] self test is off", self.loglevel)
            return self.monitor.waitForAbort(seconds)    

    def monitor_abortRequested(self):
        if (self.test):
            return 0
        else:
            xbmc.log(f"[script.nhlscores] waiting for abort", self.loglevel)
            self.monitor.abortRequested()           

    def logger(self, msg):
        xbmc.log(f"[script.nhlscores] {msg}", self.loglevel)
        if self.test:
            print(msg)
        return
    
    ###########################################################   
    def notify(self, title, msg, img=None):
    ###########################################################   
        if img is None: img = self.nhl_logo
        key = f"{title}-{msg}"
        self.logger(f"N:{key}")
        
        #self.all_messages[key] = key
        #for x in self.all_messages:
        #    self.logger(x)
        #self.all_messages.pop(key)
        self.monitor_waitForAbort(self.delay_seconds)
        self.dialog.notification(title, msg, img, self.display_milliseconds, False)

