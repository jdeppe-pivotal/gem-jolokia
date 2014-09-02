Monitoring GemFire From The Command Line
----------------------------------------

***Synopsis:*** *Easily query GemFire’s JMX statistics using command line tools*

Quite often, doing lab work or ad-hoc debugging, I want to be able to measure certain GemFire JMX attributes in real-time. Although the statistics that GemFire generates are very extensive and rich I also don’t want to have to retrieve stats from many systems and then process those after the fact. Attaching a JMX console such as jvisualvm is possible, but may also be prohibitive if my ‘lab’ happens to be running within a cloud somewhere or have restrictive firewalls in the way.

**Enter Jolokia** ([http://jolokia.org](http://jolojia.org)). 

What is it?

> *Jolokia is a JMX-HTTP bridge giving an alternative to JSR-160 connectors. It is an agent based approach with support for many platforms. In addition to basic JMX operations it enhances JMX remoting with unique features like bulk requests and fine grained security policies*

What this translates to, is that Jolokia let’s you do basic HTTP requests to retrieve JMX attributes. Jolokia is also non-intrusive and doesn’t require your code to be re-compiled to instrument it. This means that you can simply activate it with a GemFire startup option.

To try it out, [download](http://www.jolokia.org/download.html) the JVM-Agent jar and activate it when you start GemFire. A GemFire cluster federates its JMX management and monitoring infrastructure to the JMX Manager which, by default, is started on the locator. Thus, you should start your locator as follows:

    gfsh start locator --name=locator1 --port=19991 \
        --J=-javaagent:<path>/jolokia-jvm-1.2.1-agent.jar=host=0.0.0.0

The `host=0.0.0.0` option allows the Jolokia HTTP server to listen on all addresses (without this it will only listen on localhost). More details about the agent start-up options can be found [here](http://www.jolokia.org/reference/html/agents.html#agents-jvm). In these examples, we won’t be using any security. Suffice to say that, in any production or sensitive environments, you should enable Jolokia’s security features to secure the connection. Both SSL and user authentication are possible as well as restricting access to certain MBeans. Again, more information can be found on the Jolokia security reference page [here](http://www.jolokia.org/reference/html/security.html).

Once you have the locator running, you can check for proof of life by accessing the Jolokia end-point. For example:

    curl -o - http://localhost:8778/jolokia/

This should return a JSON string containing some version info.

Examing GemFire’s MBeans
------------------------

Now that we have Jolokia set up, let’s look at one of the exposed GemFire MBeans. In this example, we’ll query the System MBean:

    curl -o - http://localhost:8778/jolokia/read/GemFire:service=System,type=Distributed

This will return a whole lot of attributes. At this point it might be easier to use a browser-based REST client like the [Advanced Rest Client](https://chrome.google.com/webstore/detail/advanced-rest-client/hgmloofddffdnphfgcellkdfbfbjeloo?hl=en-US) for Chrome or [RESTClient](https://addons.mozilla.org/en-US/firefox/addon/restclient/) for Firefox to explore these results. Note that RESTClient only works when the content type returned is ‘`application/json`’. By default Jolokia will return the type as ‘`text/plain`’. To specify a specific type, append the following query string to your URLs:

    ?mimeType=application/json

Individual MBean attributes can also be retrieved with a path-like reference. Let’s retrieve the current used heap for the whole cluster

    curl -o - http://localhost:8778/jolokia/read/GemFire:service=System,type=Distributed/UsedHeapSize

Produces:

    {
        "timestamp": 1401989922,
        "status": 200,
        "request": {
            "mbean": "GemFire:service=System,type=Distributed",
            "attribute": "UsedHeapSize",
            "type": "read"
        },
        "value": 109096
    }

Even multiple attributes can be retrieved by specifying them as a comma-separated list, for example: `UsedHeapSize,TotalHeapSize`. This, of course, reduces the number of requests and bandwidth required to retrieve data. Retrieving multiple attributes returns a slightly different JSON:

    {
        "timestamp": 1401990036,
        "status": 200,
        "request": {
            "mbean": "GemFire:service=System,type=Distributed",
            "attribute": [
                "UsedHeapSize",
                "TotalHeapSize"
            ],
            "type": "read"
        },
        "value": {
            "UsedHeapSize": 110548,
            "TotalHeapSize": 643242
        }
    }

Notice that the value is now returned as an object and the values need to be retrieved using their attribute names as keys.

Jolokia also allows one to wildcard the object name key properties. Although the previous MBean provides a federated view of heap usage, individual member MBeans could also be queried for their specific heap usage:

    curl -o - http://localhost:8778/jolokia/read/GemFire:type=Member,member=*/CurrentHeapSize

Using the wildcard on the object name key ‘member’ retrieves the given attribute from all matching MBeans:

    {
        "timestamp": 1401990478,
        "status": 200,
        "request": {
            "mbean": "GemFire:member=*,type=Member",
            "attribute": "CurrentHeapSize",
            "type": "read"
        },
        "value": {
            "GemFire:member=Subscriber_w2-2013-lin-06_03,type=Member": {
                "CurrentHeapSize": 2127
            },
            "GemFire:member=Subscriber_w2-2013-lin-09_01,type=Member": {
                "CurrentHeapSize": 2440
            },
        ...
    }    

Script It
---------

Now that we have the basics of using Jolokia in place, we can incorporate this into some useful scripts. Although GemFire provides the gfsh command shell, gfsh sometimes doesn’t have the exact information we may be after. For example, a common question asked is: ‘How can I tell if my rebalance operation is complete?’. Or: ‘How full are my Async queues?’.

The presented python script uses Jolokia to answer these questions in a concise way.

In order to determine if a rebalance is complete, we can look at the changes in ‘*BucketCount*’ of each member hosting the region, and wait for the changes to stop. Method `check_rebalance_in_progress` does that and returns a number indicating how the number of buckets hosted by each member, changed over the given time interval. Once this number is 0, the rebalance is complete. (In some cases, this may produce a false positive if buckets are large enough that their time to replicate exceeds the given sleep time. If you feel this may be happening, simply increase the sleep time in the script).

The queries/options, provided by the script are:

 - **--member-count**: Returns a count of all members (excluding locators) in the cluster.
 - **--get-regions**: Returns a list of all regions.
 - **--check-rebalance [/region]**: Returns a number indicating the change in buckets across all members. An optional region name can be provided otherwise this will apply to all regions in the cluster.
 - **--queue-size [queue]**: Returns the queue size of all Asynchronous Event Queues in the cluster. An optional queue name can be provided to target a specific queue.

The script is not meant to be exhaustive, but is provided as an example and starting point to add your own specific options in order to query your GemFire JMX statistics more effectively.

Have fun using Jolokia and querying GemFire’s JMX statistics!

**References:**

 - Jolokia: [www.jolokia.org](www.jolokia.org)
 - GemFire: [gemfire.docs.gopivotal.com/index.html?q=/about_gemfire.html](gemfire.docs.gopivotal.com/index.html?q=/about_gemfire.html)
