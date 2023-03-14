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


def is_between(now, start, end):
    is_between = False

    is_between |= start <= now <= end
    is_between |= end < start and (start <= now or now <= end)

    return is_between


class Scores:

    def __init__(self):
        self.addon = xbmcaddon.Addon()
        self.addon_path = xbmcvfs.translatePath(self.addon.getAddonInfo('path'))
        self.local_string = self.addon.getLocalizedString
        self.ua_ipad = 'Mozilla/5.0 (iPad; CPU OS 8_4 like Mac OS X) AppleWebKit/600.1.4 (KHTML, like Gecko) Mobile/12H143 ipad nhl 5.0925'
        self.nhl_logo = os.path.join(self.addon_path,'resources','nhl_logo.png')
        self.api_url = 'http://statsapi.web.nhl.com/api/v1/schedule?date=%s&expand=schedule.teams,schedule.linescore,schedule.scoringplays'
        self.headshot_url = 'http://nhl.bamcontent.com/images/headshots/current/60x60/%s@2x.png'
        #aee colors.xml in kodi app
        self.score_color = 'FF90EE90'    #lightgreen
        self.score_color_other_team = 'FFFFFAF0'  #floralwhite
        self.gametime_color = 'FFFFFF00'  #yellow
        self.new_game_stats = []
        self.wait = 30
        self.display_seconds = 5
        self.display_milliseconds = self.display_seconds * 1000
        self.delay_seconds = 1
        self.delayy_milliseconds = self.delay_seconds * 1000
        self.dialog = xbmcgui.Dialog()
        self.monitor = xbmc.Monitor()
        self.test = False
        # WHhy is this 25 minutes, Do I need it
        self.DAILY_CHECK_TIMER_PERIOD = 1500 #25 minutes
        self.MAX_SLEEP_TIME = 10800 #3 h0urs
        self.loglevel = xbmc.LOGINFO
        self.all_messages = {}
        self.last_json = {}

     


    def service(self):
        first_run = True
        self.addon.setSetting(id='score_updates', value='false')

        while not self.monitor.abortRequested():
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
                # thi will always be 25 minlate, for 1t interation.  self.DAILY_CHECK_TIMER_PERIOD
                if sleep_seconds < self.DAILY_CHECK_TIMER_PERIOD:
                    self.toggle_service_on()
                    self.notify(self.local_string(30300), self.local_string(30350))
                    #In above, if waiting, this still executes (probably because in debug, the libs work differently)
                    self.logger(f"running: {self.scoring_updates_on()}")
                    if self.monitor.abortRequested():
                        self.logger(f"abort requested was seen")
                    self.scoring_updates()
                    # this should be redundsnt
                    self.toggle_service_off()

                first_run = False

            self.monitor_waitForAbort(self.DAILY_CHECK_TIMER_PERIOD)
            
    ###########################################################
    # this is a forever loop looking for updates
    # I don't think any of break statements within the loop do anything
    ###########################################################
    def scoring_updates(self):
        first_time_thru = True
        old_game_stats = []
        while self.scoring_updates_on() and not self.monitor.abortRequested():
            json = self.get_scoreboard()
            self.new_game_stats.clear()
            self.logger("Games: " + str(len(json['dates'][0]['games'])))
            for game in json['dates'][0]['games']:
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
                    
                # this doesn't show end of game.. need to loop at old first?
                for new_item in self.new_game_stats:
                    if not self.scoring_updates_on(): break
                    # Check if all games have finished
                    if 'final' not in new_item['abstract_state'].lower(): all_games_finished = False
                    for old_item in old_game_stats:
                        if not self.scoring_updates_on(): break
                        if new_item['game_id'] == old_item['game_id']:
                            self.check_if_changed(new_item, old_item)

                #for old_item in old_game_stats:
                #    if not self.scoring_updates_on(): break
                #    # Check if all games have finished
                #    for new_item in new_game_stats:
                #        if not self.scoring_updates_on(): break
                ##        if 'final' not in new_item['abstract_state'].lower(): all_games_finished = False 
                #        if new_item['game_id'] == old_item['game_id']:
                #            self.check_if_changed(new_item, old_item)



                if self.test:
                    self.testing(new_item)

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
            first_time_thru = False
            # If kodi exits or goes idle stop running the script
            if self.monitor_waitForAbort(self.wait):
                self.logger("**************Abort Called**********************")
                break
                
                
    ###########################################################
    def get_new_stats(self, game):
    ###########################################################
        #video_playing = self.get_video_playing()  
        #self.logger(f"Video Playing: {video_playing}")
        ateam = game['teams']['away']['team']['abbreviation']
        hteam = game['teams']['home']['team']['abbreviation']
        current_period = game['linescore']['currentPeriod']
        if 'currentPeriodOrdinal' in game['linescore']: current_period = game['linescore']['currentPeriodOrdinal']

        desc = ''
        headshot = ''
        try:
            desc = game['scoringPlays'][-1]['result']['description']
            strength = game['scoringPlays'][-1]['result']['strength']['code']
            desc = f"({strength}) {desc}"
            # Remove Assists if there are none
            if ', assists: none' in desc: desc = desc[:desc.find(', assists: none')]
            player_id = game['scoringPlays'][-1]['players'][0]['player']['link']
            player_id = player_id[player_id.rfind('/') + 1:]
            headshot = self.headshot_url % player_id
        except:
            pass

        game_clock = game['status']['detailedState']
        if 'in progress' in game_clock.lower():
            game_clock = f"{game['linescore']['currentPeriodTimeRemaining']} {game['linescore']['currentPeriodOrdinal']}"

        # Disable spoiler by not showing score notifications for the game the user is currently watching
        #SML. I took this out
        #if ateam.lower() not in video_playing and hteam.lower() not in video_playing:
            # Sometimes goal desc are generic, don't alert until more info has been added to the feed
        if self.getSetting(id="goal_desc") != 'true' or desc.lower() != 'goal':
            self.new_game_stats.append(
                {"game_id": game['gamePk'],
                "away_name": game['teams']['away']['team']['abbreviation'],
                "home_name": game['teams']['home']['team']['abbreviation'],
                "away_score": game['linescore']['teams']['away']['goals'],
                "home_score": game['linescore']['teams']['home']['goals'],
                "game_clock": game_clock,
                "period": current_period,
                "goal_desc": desc,
                "headshot": headshot,
                "abstract_state": game['status']['abstractGameState']})

    ###########################################################
    def check_if_changed(self, new_item, old_item):
    ###########################################################
        title = None
        message = None
        img = self.nhl_logo
        self.logger("~"+str(old_item))
        self.logger("-"+str(new_item))
 
        if 'final' in new_item['abstract_state'].lower() and 'final' not in old_item['abstract_state'].lower():
            title, message = self.final_score_message(new_item)
        elif 'live' in new_item['abstract_state'].lower() and 'live' not in old_item['abstract_state'].lower():
            title, message = self.game_started_message(new_item)
        elif new_item['period'] != old_item['period'] and 'live' in new_item['abstract_state'].lower():
            # Notify user that the game has started / period has changed
            title, message = self.period_change_message(new_item)
        elif new_item['game_clock'] != old_item['game_clock'] and 'END' in new_item['game_clock']:
            # Notify user that the game has started / period has changed
            title, message = self.period_ended_message(new_item)
            
        #TODO: maybe ignore this and check goals by all_messages
        #problem may be determining which team scored, if you don't use new/old but who cartes.\
        # check baseed on old/bew
        
        elif (new_item['home_score'] != old_item['home_score'] and new_item['home_score'] > 0) \
                or (new_item['away_score'] != old_item['away_score'] and new_item['away_score'] > 0):
            # Highlight score for the team that just scored a goal
            title, message = self.goal_scored_message(new_item, old_item)
            # Get goal scorers headshot if notification is a score update
            if self.getSetting(id="goal_desc") == 'true' and new_item['headshot'] != '': img = new_item['headshot']

        if title is not None and message is not None:
            self.notify(title, message, img)
            self.monitor_waitForAbort(self.display_seconds + 5)

    ###########################################################
    def check_games_scheduled(self):
    ###########################################################
        # Check if any games are scheduled for today.
        # If so, check if any are live and if not sleep until first game starts
        sleep_seconds = 0
        json = self.get_scoreboard()
        if json['totalGames'] == 0:
            self.toggle_service_off()
            self.notify(self.local_string(30300), self.local_string(30352))
        else:
            live_games = False
            for game in json['dates'][0]['games']:
                if game['status']['abstractGameState'].lower() == 'live':
                    live_games = True
                    break

            seconds_to_start = 0
            if not live_games:
                # date found in stream is UTC
                first_game_start = self.string_to_date(json['dates'][0]['games'][0]['gameDate'], "%Y-%m-%dT%H:%M:%SZ")
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
        if self.test:
            url = self.api_url % '2022-4-18'
        else:
            url = self.api_url % self.local_to_pacific()
            
        try:    
            headers = {'User-Agent': self.ua_ipad}
            r = requests.get(url, headers=headers)
            self.last_json = r.json()
        except:
            pass
        return self.last_json
                
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
        
    def final_score_message(self, new_item):
        # Highlight score of the winning team
        title = self.local_string(30355)
        if new_item['away_score'] > new_item['home_score']:
            away_score = f"[COLOR={self.score_color}]{new_item['away_name']} {new_item['away_score']}[/COLOR]"
            home_score = f"{new_item['home_name']} {new_item['home_score']}"
        else:
            away_score = f"{new_item['away_name']} {new_item['away_score']}"
            home_score = f"[COLOR={self.score_color}]{new_item['home_name']} {new_item['home_score']}[/COLOR]"

        game_clock = f"[COLOR={self.gametime_color}]{new_item['game_clock']}[/COLOR]"
        message = f"{away_score}    {home_score}    {game_clock}"
        return title, message

    def game_started_message(self, new_item):
        title = self.local_string(30358)
        message = f"{new_item['away_name']} vs {new_item['home_name']}"
        return title, message

    def period_change_message(self, new_item):
        # Notify user that the game has started / period has changed
        title = self.local_string(30370)
        message = f"{new_item['away_name']} {new_item['away_score']}    " \
                  f"{new_item['home_name']} {new_item['home_score']}   " \
                  f"[COLOR={self.gametime_color}]{new_item['period']} has started[/COLOR]"

        return title, message

    def period_ended_message(self, new_item):
        # Notify user that the game has started / period has changed
        title = self.local_string(30370)
        message = f"{new_item['away_name']} {new_item['away_score']}    " \
                  f"{new_item['home_name']} {new_item['home_score']}   " \
                  f"[COLOR={self.gametime_color}]{new_item['game_clock']} [/COLOR]"

        return title, message

    def goal_scored_message(self, new_item, old_item):
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
            message = new_item['goal_desc']

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
            time.sleep(seconds)
            return
        else:
            return self.monitor.waitForAbort(seconds)        

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

