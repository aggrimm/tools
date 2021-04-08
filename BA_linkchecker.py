"""
Blue Accounting bad links checker
Check links, create csv report on broken links and email to issue leads. 
modified from https://xtrp.io/blog/2019/11/09/a-quick-python-script-to-find-broken-links/
A Grimm, April 2021
"""

#libs
import requests
from requests.adapters import HTTPAdapter
from requests.packages.urllib3.util.retry import Retry
import sys, os
from bs4 import BeautifulSoup
from urllib.parse import urlparse
from urllib.parse import urljoin
import urllib3
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
import csv
import win32com.client as win32
import pandas as pd
import datetime as datetime
from collections import Counter


#site to check
site = "https://www.blueaccounting.org/"

#setup
link_count = 0
searched_links = []
searched_pages = []
link_results = []
print("ok")


# generate lists of checked and broken links
def getLinksFromHTML(html):
    def getLink(el):
        #return a tuple of link text and href
        return (el.get_text(), el.get('href'))
        #return el['href']
    return list(map(getLink, BeautifulSoup(html, features="html.parser").select("a")))

def find_broken_links(domainToSearch, URL, parentURL, linkname):
    #print("getting started")
    if (not (URL in searched_links)) and (not URL.startswith("mailto:")) and (not ("javascript:" in URL)) and (not URL.endswith(".png")) and (not URL.endswith(".jpg")) and (not URL.endswith(".jpeg")):
        #time.sleep(3)
        try:
            #requestObj = requests.get(URL);
            # retry on failure
            link_count =+ 1
            #print(link_count + ' --- testing ' + URL + ' from ' + parentURL)
            session = requests.Session()
            retry_Strategy = Retry(total = 10, connect=3, redirect = 3, status=0, backoff_factor=1)
            adapter = HTTPAdapter(max_retries=retry_Strategy)
            session.mount('http://', adapter)
            session.mount('https://', adapter)
            requestObj = session.get(URL, timeout = 10, verify = False)
            searched_links.append(URL)
            searched_pages.append(parentURL)
            if(requestObj.status_code == 404):
                result = (URL, parentURL, linkname, str(requestObj.status_code))
                link_results.append(result)
                print("BROKEN: link " + URL + " from " + parentURL)
            else:
                #print("NOT BROKEN: link " + URL + " from " + parentURL)
                if urlparse(URL).netloc == domainToSearch:
                    for link in getLinksFromHTML(requestObj.text):
                        #print(link[0]," ha! ",link[1])
                        find_broken_links(domainToSearch, urljoin(URL, link[1]), URL, link[0])
        except Exception as e:
            print("ERROR: " + str(e));
            searched_links.append(domainToSearch)
            

find_broken_links(urlparse(site).netloc, site, "", "")

# assign issues to all broken links
prevtag = ''
prevtext = ''
issuetag = '/issue/'
typetag = '/type/'
for index,link in enumerate(link_results):
    last = link_results[-1]
    parentpage = link[2]
    #print(parentpage)
    page = requests.get(parentpage)
    gt = getLinksFromHTML(page.text)
    #print(gt)
    issue = 'Undefined'
    for i, tup in enumerate(gt):
        if tup[-1] is None:
            pass
        else:
            if issuetag in tup[-1] and typetag in prevtag:
                print (tup[0])
                issue = tup[0]
            elif issuetag in prevtag and typetag in tup[-1]:
                print (prevtext)
                issue = prevtext
            prevtag = tup[-1]
            prevtext = tup[0]
    if issue == 'Undefined': # deal with pages like https://www.blueaccounting.org/page/us-clean-water-act-impairment-listing-process#main-content
        soup = BeautifulSoup(page.text)
        span = soup.find_all('span')
        prevclass = 0
        for s in span:
            if s.has_attr('class') and s['class'][0] == 'label-return-to':
                prevclass = 1
            elif prevclass == 1:
                issue = s.a.get_text()
                prevclass = 0
        print(issue)
    print (link[1],' : ',issue)
    
    link = (issue, link[1],link[2],link[3],link[4])
    link_results[index] = link

## Generate csv reports
email_list = pd.read_csv('BA_brokenlinkcontacts.csv')
names = email_list['Name']
emails = email_list['Email'].unique()
issues = email_list['Issue']
group = email_list.groupby('Email')
df2 = group.apply(lambda x: x['Issue'].unique())

for email in emails:
    print(email)
    e = '_'.join(df2[email].astype(str))
    print (e)
    counter = 0
    for i in df2[email]:
        for tup in link_results:
            counter += tup.count(i)
    print(counter)
    if counter > 0 or e == 'All_Issues':
        fname = 'BA_BrokenLinks_'+e+'_'+datetime.today().strftime('%Y-%m-%d') + '.csv'
        if not os.path.isfile(fname):
            with open(fname,'w',newline='') as out:
                csv_out=csv.writer(out)
                csv_out.writerow(['Issue','URL','Page','Link Text','Status'])
                link_results.sort()
                if e == 'All_Issues':
                    for row in link_results:
                        csv_out.writerow(row)
                else:
                    for row in link_results:
                        if row[0] == issue:
                            csv_out.writerow(row)

        outlook = win32.Dispatch('outlook.application')
        mail = outlook.CreateItem(0)
        mail.To = email
        mail.Subject = 'Blue Accounting broken links update'
        #mail.Body = 'Hey there!'
        mail.HTMLBody =\
        ' <html> ' \
        ' <body>' \
        ' <p>Hey there!<br><br>'\
        ' This is an automatically generated notification about broken links on blueaccounting.org.<br>' \
        ' You are currently receiving broken link updates for the following issues:<br><br>' \
        + e.replace("_", " ") + '<br><br>'\
        ' A list of broken links and the pages on which they appear is attached.<br>'\
        ' If you would like to change who receives these updates, please let Amanda know.<br>'\
        ' </p>' \
        ' </body>' \
        '</html>'

        # Attach a file to the email
        attachment = os.path.abspath(fname)
        mail.Attachments.Add(attachment)

        mail.Send()

# results
print ("=" * 26)
print ("|| Link Checker Results ||")
print ("=" * 26)
print ("Pages Checked: {}".format(len(searched_pages)))
print ("Links Checked: {}".format(len(searched_links)))
print ("Unique Broken Links Found: {}".format(len(link_results)))


print('done')