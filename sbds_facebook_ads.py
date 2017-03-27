#!env/bin/python3

# Interesting URLS:
# https://developers.facebook.com/docs/marketing-api/buying-api
# https://developers.facebook.com/docs/marketing-api/insights-api
# https://developers.facebook.com/docs/marketing-api/insights/action-breakdowns/v2.7
# https://developers.facebook.com/tools/explorer

# To test, create a sandbox application, and create manually the ads (follow buying API docs)
# but it is still (2017-02-01) quite limited; no ads and no insights

import serverboards, sys, datetime
from facebookads.api import FacebookAdsApi
from facebookads import objects

try:
    import settings
    FacebookAdsApi.init(settings.APP_ID, settings.APP_SECRET, settings.ACCESS_TOKEN)
    print("Using default config from settings.py")
except:
    pass

@serverboards.rpc_method
def get_accounts():
    def decorate(x):
        return {
            "value": x["id"],
            "name": x["name"]
        }
    me = objects.AdUser(settings.AD_USER)
    return [decorate(x) for x in me.get_ad_accounts(["id", "name"])]

@serverboards.rpc_method
def get_campaigns(account_id):
    fields = ["id","name"]
    def decorate(x):
        return {
            "value": x["id"],
            "name": x["name"]
        }

    account = objects.AdAccount(account_id)
    return [decorate(x) for x in account.get_campaigns(fields)]

@serverboards.rpc_method
def get_adsets(campaign_id):
    fields = ["id","name"]
    def decorate(n,x):
        return {
            "value": x["id"],
            "name": x.get("name", "Adset #%s"%n)
        }

    account = objects.Campaign(campaign_id)
    return [decorate(n, x) for n, x in enumerate(account.get_ad_sets(fields))]

@serverboards.rpc_method
def get_ads(adset_id):
    fields = ["id","name"]
    def decorate(n,x):
        return {
            "value": x["id"],
            "name": x.get("name", "Ad #%s"%n)
        }

    adset = objects.AdSet(adset_id)
    return [decorate(n, x) for n, x in enumerate(adset.get_ads(fields))]

@serverboards.rpc_method
def get_possible_insights(service=None, **kwargs):
    if service:
        service=service["config"]
        FacebookAdsApi.init(
            service["app_id"],
            service["app_secret"],
            service["access_token"]
            )
    ret=[]
    for acc in get_accounts():
        ret.append({"value": "account/%s"%acc["value"], "name": acc["name"]})
        for camp in get_campaigns(acc["value"]):
            ret.append({"value": "campaign/%s"%camp["value"], "name": "-" + camp["name"]})
            for adset in get_adsets(camp["value"]):
                ret.append({"value": "adset/%s"%adset["value"], "name": "--" + adset["name"]})
                for ad in get_ads(adset["value"]):
                    ret.append({"value": "ad/%s"%adset["value"], "name": "---" + adset["name"]})
    return ret

@serverboards.rpc_method
def get_insights(insight_id=None, timerange=None, fields=None, action_breakdown=False, service=None):
    if service:
        FacebookAdsApi.init(
            service["app_id"],
            service["app_secret"],
            service["access_token"]
            )

    if not timerange:
        today = datetime.datetime.now()
        timerange={
            "since": (today - datetime.timedelta(days=7)).strftime("%Y-%m-%d"),
            "until": today.strftime("%Y-%m-%d")
        }
    if not fields:
        fields = "call_to_action_clicks,canvas_avg_view_percent,impressions,social_clicks,website_clicks,ctr".split(",")

    params = {
            'time_range': timerange,
    }

    if action_breakdown:
        params['action_breakdown'] = 'action_type'
    else:
        params['time_increment'] = '1'
    cdata=None
    if insight_id.startswith("account/"):
        cdata=get_account_insights(insight_id[8:], fields, params)
    if insight_id.startswith("campaign/"):
        cdata=get_campaign_insights(insight_id[9:], fields, params)
    if insight_id.startswith("adset/"):
        cdata=get_adset_insights(insight_id[6:], fields, params)
    if insight_id.startswith("ad/"):
        cdata=get_ad_insights(insight_id[3:], fields, params)

    if not cdata:
        return {}

    data=None
    if action_breakdown:
        data={}
        dt=cdata[0]
        for f in fields:
            name = ID_TO_NAME.get(f, f)
            data[name]=dt[f]
    else:
        data=[]
        for f in fields:
            v=[]
            for cd in cdata:
                date=cd["date_start"]
                v.append([date, cd[f]])
            name = ID_TO_NAME.get(f, f)
            data.append({'name':name, 'values': v})

    return data

def get_account_insights(id, fields, params):
    account = objects.AdAccount(id)
    return list(account.get_insights(params=params, fields=fields ) )
def get_campaign_insights(id, fields, params):
    campaign = objects.Campaign(id)
    return list(campaign.get_insights(params=params, fields=fields ) )
def get_adset_insights(id, fields, params):
    adset = objects.AdSet(id)
    return list(adset.get_insights(params=params, fields=fields ) )
def get_ad_insights(id, fields, params):
    ad = objects.Ad(id)
    return list(ad.get_insights(params=params, fields=fields ) )

def create_campaign(account_id, name, objective, status):
    account = objects.AdAccount(account_id)

    campaign = objects.Campaign(parent_id = account.get_id_assured())
    campaign[objects.Campaign.Field.name]=name
    campaign[objects.Campaign.Field.objective]=objective
    campaign[objects.Campaign.Field.configured_status]=status

    print(campaign.remote_create())

def define_targeting(q):
    from facebookads.adobjects.targetingsearch import TargetingSearch
    from facebookads.adobjects.targeting import Targeting

    params = {
        'q': q,
        'type': 'adinterest',
    }

    interests = TargetingSearch.search(params=params)

    targeting = {
        Targeting.Field.geo_locations: {
            Targeting.Field.countries: ['US'],
        },
        Targeting.Field.interests: interests,
    }
    return targeting


def create_adset(account_id, campaign_id, targeting, name):
    import datetime
    from facebookads.adobjects.adset import AdSet

    today = datetime.date.today()
    start_time = str(today + datetime.timedelta(weeks=1))
    end_time = str(today + datetime.timedelta(weeks=2))

    adset = AdSet(parent_id=account_id)
    adset.update({
        AdSet.Field.name: name,
        AdSet.Field.campaign_id: campaign_id,
        AdSet.Field.daily_budget: 1000,
        AdSet.Field.billing_event: AdSet.BillingEvent.impressions,
        AdSet.Field.optimization_goal: AdSet.OptimizationGoal.reach,
        AdSet.Field.bid_amount: 2,
        AdSet.Field.targeting: targeting,
        AdSet.Field.start_time: start_time,
        AdSet.Field.end_time: end_time,
    })

    as_ = adset.remote_create(params={
        'status': AdSet.Status.paused,
    })
    return as_

def create_adimage(account_id, imagepath):
    from facebookads.adobjects.adimage import AdImage

    image = AdImage(parent_id=account_id)
    image[AdImage.Field.filename] = imagepath
    image.remote_create()

    return image[AdImage.Field.hash]


def create_creative(account_id, name, caption, message, link, imagehash, page_id):
    AdCreative=objects.AdCreative
    from facebookads.adobjects.adcreativelinkdata import AdCreativeLinkData
    from facebookads.adobjects.adcreativeobjectstoryspec import AdCreativeObjectStorySpec

    link_data = AdCreativeLinkData()
    link_data[AdCreativeLinkData.Field.message] = message
    link_data[AdCreativeLinkData.Field.link] = link
    link_data[AdCreativeLinkData.Field.caption] = caption
    link_data[AdCreativeLinkData.Field.image_hash] = imagehash

    object_story_spec = AdCreativeObjectStorySpec()
    object_story_spec[AdCreativeObjectStorySpec.Field.page_id] = page_id
    object_story_spec[AdCreativeObjectStorySpec.Field.link_data] = link_data

    creative = AdCreative(parent_id=account_id)
    creative[AdCreative.Field.name] = name
    creative[AdCreative.Field.object_story_spec] = object_story_spec
    creative.remote_create()

    print(creative)
    return creative

def create_ad(account_id, adset_id, creative_id, name):
    from facebookads.adobjects.ad import Ad

    ad = Ad(parent_id=account_id)
    ad[Ad.Field.name] = name
    ad[Ad.Field.adset_id] = adset_id
    ad[Ad.Field.creative] = {
        'creative_id': creative_id,
    }
    ad.remote_create(params={
        'status': Ad.Status.paused,
    })
    return ad

ID_TO_NAME={
    "like": "Likes",
    "link_click": "Link clicks",
    "post_like": "Post Likes",
    "comment": "Comments",
    "mobile_app_install": "Mobile App Installations",
    "call_to_action_clicks": "CTA Clicks",
    "ctr": "CTR",
    "canvas_avg_view_percent": "Avg % canvas viewed",
    "impressions": "Impressions",
    "social_clicks": "Social Clicks",
    "website_clicks": "Website Clicks",

}

@serverboards.rpc_method
def campaign_insights(campaign_id=None):
    if not campaign_id:
        accounts = get_accounts()
        campaigns=get_campaigns(account)
        campaign_id = campaigns[0]["value"]
    cdata=get_campaign_insights(campaign_id)
    data={}
    for dt in cdata["data"][0]["actions"]:
        name = dt["action_type"]
        name = ID_TO_NAME.get(name, name)
        data[name]=dt["value"]
    return data

@serverboards.rpc_method
def check_rules(*_args, **_kwargs):
    rules = serverboards.rpc.call("rules.list", trigger="serverboards.facebookads/trigger", is_active=True)
    for r in rules:
        params = r["trigger"]["params"]
        service_id = params["service"]["config"]
        insight = params["insight"]
        field = params["field"]
        end = datetime.datetime.now().strftime("%Y-%m-%d")
        state = False
        limit = float(params["value"])
        cond = params["condition"] or ">"
        data = get_insights(
            insight_id=insight,
            timerange={"since": end, "until": end},
            fields=[field],
            service=service_id)
        value = float(data[0]["values"][0][1])

        if cond == "<":
            state = value < limit
        elif cond == "<=":
            state = value <= limit
        elif cond == ">":
            state = value > limit
        elif cond == ">=":
            state = value >= limit
        state = "ok" if state else "nok"
        serverboards.info("Facebook Ads Rule check %s: %s %s %s -> %s"%(r["uuid"], value, cond, limit, state))
        serverboards.rpc.event("rules.trigger", id=r["uuid"], state=state, value=value)



def test():
    for i in  get_possible_insights():
        print(i)
        print(get_insights(i["value"]))
        #print()
        continue

if __name__=='__main__':
    if len(sys.argv)>1 and sys.argv[1]=="test":
        test()
    else:
        serverboards.loop()
