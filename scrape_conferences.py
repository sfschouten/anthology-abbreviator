import urllib2


from bs4 import BeautifulSoup


ACL_ANTHOLOGY_URL = 'https://aclanthology.org/'



def scrape():
    
    # main page
    c = urllib2.urlopen(page)
    soup = BeautifulSoup(c.read(), 'html.parser')


    # process venues


        
        # process proceedings
        
        # process year
        # by year, find what is common to each proceedings title





if __name__ == '__main__':
    scrape()
