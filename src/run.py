import os
import time
import re
from slackclient import SlackClient
from slackclient.server import SlackLoginError
from stackapi import StackAPI
from googleapiclient.discovery import build

# constants
RTM_READ_DELAY = 1 # 1 second delay between reading from RTM
COMMANDS = ["ask", "question"]
MENTION_REGEX = "^<@(|[WU].+?)>(.*)"
SLACK_BOT_TOKEN = os.environ.get('SLACK_BOT_TOKEN')
GOOGLE_DEVELOPER_KEY = os.environ.get('GOOGLE_DEVELOPER_KEY')
CX_TOKEN = os.environ.get('CX_TOKEN')
MAX_ANSWERS = 3

print('Initializing Services')
# instantiate Slack client
slack_client = SlackClient(SLACK_BOT_TOKEN)
# instantiate Stackoverflow API
SITE = StackAPI('stackoverflow')
# instantiate Google Search client
service = build("customsearch", "v1", developerKey=GOOGLE_DEVELOPER_KEY)


# starterbot's user ID in Slack: value is assigned after the bot starts up
starterbot_id = None

def parse_bot_commands(slack_events):
    """
        Parses a list of events coming from the Slack RTM API to find bot commands.
        If a bot command is found, this function returns a tuple of command and channel.
        If its not found, then this function returns None, None.
    """
    for event in slack_events:
        if event["type"] == "message" and not "subtype" in event:
            user_id, message = parse_direct_mention(event["text"])
            if user_id == starterbot_id:
                ts = event['ts']
                return message, event
    return None, None

def parse_direct_mention(message_text):
    """
        Finds a direct mention (a mention that is at the beginning) in message text
        and returns the user ID which was mentioned. If there is no direct mention, returns None
    """
    matches = re.search(MENTION_REGEX, message_text)
    # the first group contains the username, the second group contains the remaining message
    return (matches.group(1), matches.group(2).strip()) if matches else (None, None)

def handle_command(command, event):
    """
        Executes bot command if the command is known
    """
    channel = event['channel']
    command_prefix = command.split()[0]
    command_suffix = ' '.join(command.split()[1:])
    
    # Finds and executes the given command, filling in response
    response = ''
    # This is where you start to implement more commands!
    if command_prefix in COMMANDS:
        #### GOOGLE CUSTOM
        res = service.cse().list(q=command_suffix,cx=CX_TOKEN,num=MAX_ANSWERS).execute()
            # Sends the response back to the channel
        if res.get('items'):
            for r in res['items']:
                link = r['link']
                question_id = link.split('/')[4]
                answers = SITE.fetch('questions/%s/answers' %question_id, sort='votes', filter='!4*mUMjFEjVugxwySf')
                reference_response = ':globe_with_meridians: *Reference:* %s' %link
                if not answers['items']:
                    r=slack_client.api_call(
                    "chat.postMessage",
                    channel=channel,
                    unfurl_links=True,
                    thread_ts = event['ts'],
                    text=reference_response + '\nI was not able to fetch the answer for this reference, but take a look at the link above :)')
                else:
                    try:
                        best_score = answers['items'][0]
                    except:
                        best_score = {}
                        best_score['body_markdown'] = ''
                    accepted_answer = {}
                    accepted_answer['body_markdown'] = 'No accepted answer yet'
                    for a in answers['items']:
                        if a['is_accepted'] == True:
                            accepted_answer = a
                            break
                    accepted_response = '>>> :white_check_mark: *Accepted Answer:* %s' %accepted_answer['body_markdown']
                    best_score_response = ':top: *Best Score Answer:* %s' %best_score['body_markdown']
                    if accepted_answer == best_score:
                        best_score_response = ''
                    r=slack_client.api_call(
                        "chat.postMessage",
                        channel=channel,
                        unfurl_links=True,
                        thread_ts = event['ts'],
                        text=reference_response + '\n' + accepted_response + '\n' + best_score_response)
        else:
            response = 'Ops! No results for: "%s"' %(command_suffix)
            r=slack_client.api_call(
                "chat.postMessage",
                channel=channel,
                unfurl_links=True,
                thread_ts = event['ts'],
                text=response)
    elif command_prefix == 'help':
        response = '''*Augusta Ada King, Countess of Lovelace* (nee Byron; 10 December 1815 - 27 November 1852) was an English mathematician and writer, chiefly known for her work on Charles Babbage's proposed mechanical general-purpose computer, the Analytical Engine. She was the first to recognise that the machine had applications beyond pure calculation, and published the first algorithm intended to be carried out by such a machine. As a result, she is sometimes regarded as the first to recognise the full potential of a "computing machine" and the first computer programmer.\n\nCommands available *{}*.'''.format(COMMANDS)
        r=slack_client.api_call(
                "chat.postMessage",
                channel=channel,
                unfurl_links=True,
                thread_ts = event['ts'],
                text=response)
    else:
        response = "Not sure what you mean. Try *{}*.".format(COMMANDS)
        r=slack_client.api_call(
                "chat.postMessage",
                channel=channel,
                unfurl_links=True,
                thread_ts = event['ts'],
                text=response)

if __name__ == "__main__":
    if slack_client.rtm_connect(with_team_state=False):
        print("Slackbot connected and running!")
        # Read bot's user ID by calling Web API method `auth.test`
        starterbot_id = slack_client.api_call("auth.test")["user_id"]
        while True:
            command, event = parse_bot_commands(slack_client.rtm_read())
            if command:
                handle_command(command, event)
            time.sleep(RTM_READ_DELAY)
    else:
        print("Connection failed. Exception traceback printed above.")
