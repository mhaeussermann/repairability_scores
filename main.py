import requests as req
import time
from datetime import datetime
import json
import re
import csv
from bs4 import BeautifulSoup

# Set API URL
API_BASE_URL = 'https://www.ifixit.com/api/2.0'

def search_guides(term='repairability', filter_param='guide'):
  response = req.get('https://www.ifixit.com/api/2.0/search/{}?filter={}'.format(term, filter_param))
  data = response.json()

  #find out the number of results
  total_num = data['totalResults']

  #search result data will be appended to this list
  data_list = []

  #iterate through search results
  for offset in range(0, total_num, 20):
    url = 'https://www.ifixit.com/api/2.0/search/{}?filter={}&offset={}'.format(term, filter_param, offset)              
    response = req.get(url=url).json()
    for i in response['results']:
      data_list.append(i)       
    print(offset)
    time.sleep(2)
    #print(data_list[0][0]['title'])

  # save the list of search results
  with open('test.json', 'w') as fout:
    json.dump(data_list , fout)


def get_guides():
  # open list of search results
  with open('test.json') as json_file:
    search_results = json.load(json_file)

  # guide data will be appended to this list
  raw_data = []

  #iterate through search results
  for i in search_results:
    response_item = req.get('https://www.ifixit.com/api/2.0/guides/{}'.format(i['guideid']))
    item = response_item.json()   
    raw_data.append(item)
    # wait 5 seconds to be thoughful of API stressing
    time.sleep(5)

  # save guide data to json
  with open('raw_data_repairability.json', 'w') as fout:
    json.dump(raw_data , fout)

def filter_data(file = 'raw_data_repairability.json'):
  # open file with list of guides/teardowns
  with open(file) as json_file:
    devices = json.load(json_file)

  # define list where the dicts will be appended to as well as a list to save the guides where no score is found
  listOfGuides = []
  noScoreFound = []
  
  # iterate through guides
  for i in devices:
    # define dict to save needed information 
    singularGuides = {}

    # define lists to save specific lines of text
    finalThoughts = []
    positiveArgs = []
    neutralArgs = []
    negativeArgs = []

    # set userTeardown and nonEnglish to filter teardowns by community members and non-english ones
    userTeardown = False
    nonEnglish = False

    # check for unofficial teardowns
    try: 
      if i['flags']:
        for k in i['flags']:
          if k['flagid'] == 'GUIDE_USER_CONTRIBUTED':
            userTeardown = True
    except KeyError:
      pass
    
    # check for non-english teardowns
    try:
      if i['langid'] != 'en':
        nonEnglish = True
    except KeyError:
      pass

    # if both arguments are false: extract data, else: skip the guide/teardown
    if userTeardown != True and nonEnglish != True:
      # use try to catch API results with unexpected results
      try:
        # test for the loop
        #print("ID {}, Steps: {}, {}".format(i['guideid'], len(i['steps']), i['url']))

        # define data saved from guide/teardown
        singularGuides['guideid'] = i['guideid']
        singularGuides['title'] = i['title']
        singularGuides['author'] = i['author']['username']
        singularGuides['stepsLength'] = len(i['steps'])
        singularGuides['url'] = i['url']
        singularGuides['category'] = i['category']
        singularGuides['difficulty'] = i['difficulty']
        singularGuides['createdDate'] = datetime.utcfromtimestamp(i['created_date']).strftime('%Y-%m-%d %H:%M:%S')
        singularGuides['publishedDate'] = datetime.utcfromtimestamp(i['published_date']).strftime('%Y-%m-%d %H:%M:%S')
        singularGuides['modifiedDate'] = datetime.utcfromtimestamp(i['modified_date']).strftime('%Y-%m-%d %H:%M:%S')

        # check for final thoughts (last step) and extract arguments
        if len(i['steps']) >= 1:
          for j in i['steps'][-1]['lines']:
            if j['bullet'] == 'black':
              finalThoughts.append(j['text_raw'])
            elif j['bullet'] == 'green':
              positiveArgs.append(j['text_raw'])
            elif j['bullet'] == 'yellow':
              neutralArgs.append(j['text_raw'])
            elif j['bullet'] == 'red':
              negativeArgs.append(j['text_raw'])
        singularGuides['finalThoughts'] = ' '.join(finalThoughts)
        singularGuides['positiveArgs'] = positiveArgs
        singularGuides['positiveArgsNum'] = len(positiveArgs)
        singularGuides['neutralArgs'] = neutralArgs
        singularGuides['neutralArgsNum'] = len(neutralArgs)
        singularGuides['negativeArgs'] = negativeArgs
        singularGuides['negativeArgsNum'] = len(negativeArgs)

        # extract repairability score
        try:
          rating = re.search('(^a(?=\s)|one|two|three|four|five|six|seven|eight|nine|ten|[0-9]+) out of', singularGuides['finalThoughts'].replace('\'',''), re.IGNORECASE).group(1)
          singularGuides['rating'] = rating
          pass
        except:
          # set rating to none if regex fails
          rating = None
          noScoreFound.append(singularGuides['title'])
          singularGuides['rating'] = rating
          pass
        
        # extract tools
        if len(i['tools']) > 1:
          toolShed = []
          for z in i['tools']:
            toolShed.append(z['text'])
          singularGuides['tools'] = toolShed
        elif len(i['tools']) == 1:
          singularGuides['tools'] = i['tools'][0]['text']
        else:
          singularGuides['tools'] = None        
        singularGuides['toolsAmt'] = len(i['tools'])

        # get comments
        listOfComments = []
        if len(i['comments']) > 1:
          for z in i['comments']:
            comments = {}
            comments['author'] = z['author']['username']
            comments['text'] = z['text_raw']
            comments['createdDate'] = datetime.utcfromtimestamp(z['date']).strftime('%Y-%m-%d %H:%M:%S')
            listOfComments.append(comments)
          singularGuides['comments'] = listOfComments
        elif len(i['comments']) == 1:
          comments = {}
          comments['author'] = i['comments'][0]['author']['username']
          comments['text'] = i['comments'][0]['text_raw']
          comments['createdDate'] = datetime.utcfromtimestamp(i['comments'][0]['date']).strftime('%Y-%m-%d %H:%M:%S')
          listOfComments.append(comments)
          singularGuides['comments'] = listOfComments
        else:
          singularGuides['comments'] = None
        singularGuides['commentsAmt'] = len(i['comments'])

        # get view counter statistics
        views = view_statistics(i['url'])
        singularGuides['viewsLastWeek'] = views['Past 7 Days']
        singularGuides['viewsLastMonth'] = views['Past 30 Days']
        singularGuides['viewsAllTime'] = views['All Time']

        # append the guide to the list
        print('Add {} to the list'.format(i['title']))
        listOfGuides.append(singularGuides)
      
      # catch errors in the guide/teardown data
      except KeyError:
        print("Issue with {}".format(i))
        continue
  
  # print list of devices without score found and how long the list is
  print(noScoreFound)
  print(len(noScoreFound))

  # save filtered data to json
  with open('filtered_data.json', 'w') as fp:
      json.dump(listOfGuides, fp, sort_keys=True, indent=4)

  # save filtered data to csv
  keys = listOfGuides[0].keys()
  with open('tabled_data.csv', 'w', newline='')  as output_file:
      dict_writer = csv.DictWriter(output_file, keys)
      dict_writer.writeheader()
      dict_writer.writerows(listOfGuides)

def view_statistics(url):
  # get the page
  page = req.get(url, timeout=15)
  if page.status_code == 200:
    soup = BeautifulSoup(page.text, 'html.parser')

    # create soup
    statistics_container = soup.find(class_='stats-numbers-container').find_all('p')

    # create dict from statistics data
    statistics = {}
    for i in statistics_container:
      statistics[i.find(class_='statTitle').text.strip(':')] = int(i.find(class_='statValue').text.replace(',',''))

    # wait a bit to be mindful of API usage
    time.sleep(3)
    return statistics
  else:
    print('Error scraping the page: {}'.format(page.status_code))
