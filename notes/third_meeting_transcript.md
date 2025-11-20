# Third Meeting Transcript

**Transcript**

which would be fine. Like with this tool, you could set your upper limit to the top. There would be no, so for at least for a lot of the basic like physics questions, you don't want to truncate anything at the high end. However, So I guess at the high level, I wouldn't apply that. There are some cases where you do want the upper limit. And in that case, you would want to truncate. So if you set your lower bound to like 20,000, then pixels above that should just appear as 20,000. They shouldn't appear like empty, if that makes sense. And we do that sometimes for the CNN. because the CNN is bad at things with too much dynamic range. So sometimes we do want to condense the dynamic range. And so we turn down the highest pixels to some upper upper limit. Does that make sense for the at least for a threshold?

Yeah, that makes sense.

For the lower bound, I wasn't sure exactly what you meant, David, about scalar.

Yeah, I meant the question said static value, like just a number. Whereas you talked about setting the threshold in terms of a standard deviation or a multiple of a standard deviation. Right, I guess it would result in a #2. So programmatically, I don't see much of a difference there, I guess.

Exactly. Yeah. I mean, I think in practice, it's basically a static number. And then we chose that number based on the standard deviation. And you might or might not want to like update that number. for each acquisition. But the kind of the assumption is that if the assumption is that it shouldn't really be changing. If you do 100 acquisitions in a row, the noise should be about the same. And so you don't need to change your threshold. And if your noise is changing, you probably have some other problem that you don't want to just solve by, you can't just solve by changing your threshold.

It occurs to me that if you said in terms of a standard deviation, then When you change sensors, then you won't be caught off guard, it won't be wildly different.

Yeah, yep.

To go along with the, from what I've been testing with the standard deviation, it is very fast. It's able to compute it very fast and it is fairly easy to change if anything were to change. It could be something, because it's all based on the, let me pull it here out clustered it, because I put a Jupiter notebook together on it. was on the width of the ADCs, it looks like, or the channel number that they had in there. It was the standard deviation there, so I guess that if that number itself would change or could change, then it could be something to just... change a value, it wouldn't necessarily affect the thresholding itself. And it does very good at filtering out the background.

Yeah, so I wasn't sure, are you showing, are you going to show it the notebook or?

Yeah, I'm going to pull it up here. I have to pull the new branch in. While I work on that, I can just pull it up in here. Because my VS code does not like this, but I have it saved.

While I have a question about the GitLab, because we are actually needing to put all our code somewhere. We have a separate GitHub repo we're using. We got access to the GitLab you gave us, but we're not sure if we're just allowed to create a repo there or what the mechanics are.

Okay, let's come back to that in a second. But yeah, I think if you can't, if you don't, I'm not sure if you have permission to create a repo, but I can create one for you. Or, I also, if you want to, if you have another tool you're used to using, we can just use that. I'm mostly, so I mean, I'm happy we can host it in ours, but I also wanted you guys to just have access to the code that we've made. So either way it's fine.

Yeah, I went through that with the... The simulator one, too. That was a hard time to get running, but I was able to go through that and get some data simulated and see how that was working with the diffusion.

Oh, really? You ran that? Wow, okay. That's really cool.

Yeah, that was all in root files, so I wasn't exactly sure how that would translate, but I was going through all of the notebooks and it was dense, but it was pretty interesting.

I wasn't going to ask you to do the simulation, but that's really cool. You figured it out.

The one thing that I haven't been able to look at yet, though, is the actual like machine learning model for it, because the weights need an invite. It's set it on the GitLab. I can't do the thing.

Like weights and biases, you mean?

Yeah, the weights and biases for it. Let me.

I think you can get away without using that.

Without using those? Okay.

Yeah.

I'll have to go through it a little bit more. But I had pulled from everything else. I used the same values, which I believe went with the FITS data.

Cool. So you found, looks like you found some of the example file. Yeah, I see where that came from.

Yeah, it went through that and then. We had been looking at the FITS data a lot, so it's not much to open it and to plot it here. And then here was the, there wasn't much for actual FITS data. A lot of it was the simulated data. So I added a little bit here. I took some of the standard deviation part to store that. I'm working on a way now to try and think of how to actually store the clusters, because I think our general idea is to have it so that you can look at the FITS display, you can go through that, identify things that look interesting, and then just have this be like an automatic thing that you could also just look at things that are clusterized.

Yeah. great. This, by the way, is actually a different stigma than we're talking about for the threshold.

For the... Yeah, the data was greater than four times the... That's what was used and it did.

Yeah, sorry, what I mean is this code you're looking at is doing analysis on the clusters for that predetermined threshold, which you found, which you found correctly. But then there's a sigma, we calculate like sigma X and sigma Y.

Yeah, that's for the actual pixels.

That's actually, yeah, that's about like... the sigma of the charge within that cluster. That's different than the sigma we're using to define the threshold.

Yes.

Okay, just to make sure we're on the same page.

Yeah. One thing was the, it takes it in a 10 by 10. I haven't fully looked into it yet, but just the 10 by 10 matrix of the charge values. to keep things there. Some of them are so small and so close together that if I force it to do that and it's not like it doesn't fit in the range on its own, that it includes other clusters, I can try to show some of that. I have this multi-threaded, so this is able to go through two FITS files and all the HDUs, and it can cluster 20 from each and show them out in about 30 seconds.

Great.

But this is the kind of. input that it gives me, but like this one right here is 2 pixels tall, 3 wide, with a fairly low standard deviation. I did, because I was going through that PowerPoint as well, for one KEV is like the threshold for it, for any like tritium events. I believe it wouldn't be below that.

Maybe half a KV, but something like that.

Yeah, it was along those lines, but that was what I used for these. Some of these are from the ones without tritium. Let me go down a bit.

Yeah.

So here you can see one peeking through.

Yeah. So the 10 by 10 window. I mean, so first of all, these look, these look good. Most of these look real. And I would say like even that really small one you showed me looks like a real interaction. If you have a fixed size window, you're going to have cases like this one where there's overlap. And That's kind of annoying, but that's just how it is if you use a fixed size window. In this particular case, it might have been possible to separate them if you just look at continuous sets of pixels, because I think there's one column in that case that's All below threshold.

Yeah, this would be none. So I was thinking about padding it out just to meet 10 by 10. Because if I leave it alone without just adding to the capture size, I could just try and pad it out in the middle. But this was more of just to get a proof of concept and sort of catch up to where everything is. Like I think this one looks pretty good. Yep, These start to look more.

So some of those are kind of messed up and I think we're not sure, like the ones that are just single rows, if you go back. Like this? one. Yeah. That, we don't understand what this is, but there's something wrong with that. Where it shouldn't have, it's basically, it shouldn't be possible to have such sharp single row features. It should be more like the one above that if it was a physical, because the charge spreads out along the y-axis. So there's probably some charge got stuck in one pixel while it was being read out and it made a kind of artifact. So like for example, in the analysis, if you have like sigma Y is 0, or sigma X is 0, we would cut that out. Yeah, cut that out. But that's not a problem of the software. That's a problem of the data.

Yeah, it's just something stuck there.

These other ones, so then, okay, the other, this is nice. So like, yeah, that one, measured ID 4. You can see that's some track that's way bigger than 10 by 10, just cutting across here.

And maybe, it even connects to measured ID 3. Like those could, I don't know, depends how your clustering work. But those, I mean, those are obviously larger than 10 by 10, but it doesn't really matter because you can see the energy even in 10 by 10. Well, it looks like the energy is using pixels out of frame.

Yeah, I think the 605 is a bit too much. It's just cutting the capture view to graph it. The actual saved cluster. Because it'll just do a 10 by 10 around what is the greatest point. Yeah.

Okay, got it, got it. So anyway, those are badly suited to the 10 by 10, but we don't care because these are not the ones we're interested in anyway, and we just reject them with the energy.

Right. Would it still be useful to have all of them to look at or to try and classify them at some point? Maybe capture the whole thing instead of a 10 by 10?

Yeah, so I would say, yeah, for the the 10 by 10 case is really specific to tritium beta rays. But we would care about these tracks also, just not for, it's just not a tritium candidate. So like, yeah, we still want to be able to display, these are based, these are Compton electrons. Or they're basically like gamma ray interactions that give you a high energy electron. We still want to look at those sometimes. So, I think it's just a separate case. We don't we don't need like a really fancy classifier for them.

Okay, yeah. Which a lot of these from the, like these ones I feel like are very clear. I feel like this is like a perfect input for it from what we were looking at before.

That's a perfect tridium candidate.

I think I had it. I may have commented it out because I have a lot of different ways to run it. I ran a benchmark with trying to multi-thread it or just to go through them. Because plotting them all out at once isn't really feasible or wanted. So I think my idea here is just to save the array of energy and then plot it whenever it's wanted. because they're usually going pretty quick.

But isn't that, I mean, isn't that expected? Because we would do this in batches, right? So when we get data from the CCD, we cluster it. There's no one looking at it at the moment. And then we send it to the CNN, it's classified, and it's fine. So I don't think that speed matters at that point. It's more important when you are on the visual tool. So For instance, what I showed, you want to actually, I don't know, find the features, clusterize them. You want to see that fast because you're acting on a user tool. But for this track here, where you're just getting the stream of data out of the CCD and processing, I think that's fine.

Yeah, and I totally agree. And I also think the data volume it's produced kind of slowly. Like you might get a new file every 5 or 10 minutes. And so...

Okay, because that was what we were also wondering. I think we talked about that last meeting with David, was how much we were really going to be looking at.

Yeah, and that's actually the reason why I've been investigating on HDB scan, because for the user track, when you're looking at the screen on something, oh no, on a new fits image that's not been classified, because you're, I don't know, just looking into the data, just playing with it. that's when you want something fast. And that's the one you can train on the background data to discard whatever is garbage data. I don't know how you guys call it, but that's where you need speed. And in the test I was able to run, I was able to find some clusters in less than 700 milliseconds. So it's pretty fast. But tuning it, it's really complicated. to make it work. That's why I'm still playing with it. But that would be something for the human at the console. That's something different. Because from there, the idea would be that, I don't know, maybe you can create like a mask of the image. And that's something that Nick has been working on. You can create a mask of the image, apply a mask, and then... remove values or just extract features and then play with that in some other way. It's like a playground. That's the idea with the other two. And that's where I do see a need for speed. But for this one, I see more a need for precision for what Troy is showing us.

So, okay, so just to reiterate, I think you're saying there's basically, there's two processing modes. One of the processing modes is for the kind of offline analysis with the highest accuracy and precision, where speed is less essential, and that's like this one. And then there's also an online mode where you want to be able to cluster like immediately. And if you're missing some clusters for the price of speed, that's okay.

Yeah, that's yeah, that's it. And the idea is that from there you are able to maybe discover other things. Maybe this samples that you mentioned, we don't know what these are. Maybe you are able to play more with that in a visual tool because you are actually interacting with the data. And not looking for a result that maybe it was from yesterday. And maybe you missed something. I don't know. Yeah, that the idea would be to enable you to play with that, but this one here that Troy is showing us, it's for the actual results based on what you know of the data, on the constants you require to pre-multiply things, your six mass and all that kind of thing, so it, yeah, it's 2 tracks, and the way I personally be thinking is that... This is like a, it's a separate mode of the app. It could be the screen I showed you earlier, and maybe there could be like a tab where you see all the historical data, which is actually connected to what Troy is showing us here. And in that one, you browse the

cluster just how he showed us, and then you're able to do the things you want to do with your data.

Yeah, I love that idea. I would say for that implementation, the way that we typically do this in physics would be if you're worried about the clustering being slow, you have one kind of immediate processing step where you take the raw image, you do some basic calibration, thresholding, and then you do the clustering and you output a new data format that's basically a list of clusters. And you could even show like, in that, you could have like basic properties like the energy, the position, sigma X, sigma Y. And you can even have the 10 by 10 matrix for that cluster kind of stored in that new format. And so then you basically save a structure that's just kind of like a dictionary of clusters or a list of clusters. And then that already takes out kind of the heaviest, or like one of the heavier computational steps. And then you do your analysis on that list of clusters instead of like recalculating it on the fly. So that could be one way to go. I feel like, but anyway, it does, if you have another idea, it doesn't have to be factorized like that. I think it's not such huge data that you have to kind of like do this intermediate, make this intermediate format. But that's something we typically do in the past.

Yeah, I think that lines up with what we were talking about. to have those sorts of two different ways of looking at it, a more automated way. I think the real-time view of it would be similar to what Juan has been working on to look through it, and it would just be a pretty much a completely different view for it.

Good, yeah. I wanted to go back to what Juan showed at the very beginning with like this, these clustering algorithms. If you want to show your, if you could show your screen again.

Yeah, sure.

I think I totally understand where you're going with this now. I would say, or kind of like the slow, accurate mode, this clustering doesn't work well. Like it should be, it's missing like half the clusters. Yeah. And I think, which is totally fine. Yeah, no, I.

I was actually normalizing it and I took into account the smaller dimension and that's why it looks like a square. So.

Okay, No, problem. I think I was just going to say a general thing we noticed. We kind of prefer to do for the clustering stuff. We just do. It's easy enough that we can do the like a classical. clustering search, once you apply the thresholds, where you just loop through and find the connected set of pixels that are above threshold. Does that kind of algorithm make sense? Like no computer vision, just...

Yeah, so it would be like sort of a flat field. So you just step on a pixel and then you look for the connected components until you find the shape and then... When there are not, when you find a lot of zeros around that there's nothing, then you're done.

Something like that. Exactly, So that's exactly, and there's a lot of implementations of that, but that's what we call classical clustering. That basically works perfectly for this data because it's easy to set a threshold. You end up with lots of empty space, and so that becomes safe. Which I think is a little different than a lot of image analysis where there's no empty space. And so you need some machine learning to decide where the edges are.

Yeah, and that's exactly what HDB scan does. Yeah. I don't want to.

Okay. But yeah, I would just say a general, anyway, I like this if it can be faster and kind of live. But I think, I've seen other groups. focus, try to do the machine learning segmentation. And they get weird results, like they'll have the same cluster several times, like appearing in several segments, and then they miss some obvious clusters. So I think it's somehow harder to get right, and the classical one just works. So our approach has always been to do simple clustering and then do the machine learning for the classification. not for the segmentation. But anyway, I think you get it. But this is still cool if you can make it fast and live.

Yeah. Okay. I think that'll do okay.

But yeah, I wouldn't like go crazy trying to make this work perfectly because I think it's easier to just do the classical one. Sounds good. But overall, I'm really impressed actually how much you guys have already dug in so far. It's really, it's really great work. I'm happy to look at more stuff, but I kind of wanted to just say it would be cool, I think, if you guys could put together some kind of outline or like a plan for the project. Just so I love all these little, all the things you're showing, but I think it would be nice if we can kind of get on the same page about what the big picture plan will look like.

This week we're turning in some design documents for the class. But it's like a class activity. So some of us are working on some functional areas and others in other functional areas and we're supposed to. discussing a sort of a virtual forum, hey, have you considered this? Have you considered that? And then after that, we merge that. And that's where we get a full-size design of everything. I don't know. We do have our preliminary stuff pretty much ready because it has to be turned in today. So I'm hoping, I think, by The last activity should be on this Thursday when we finish the discussion. So after that, we should be in a position to kind of merge everything so you can see it. Because what we have is preliminary right now. So I don't know.

Okay, yeah, it doesn't have to be now.

I think it could be good to do the technical requirements document. We could probably share that one. That might explain. all of the ideas we have just so that we're on the same page. I think the specifics of the design may be something that can come a little bit later.

Yeah, well, actually, I think that's a bit outdated from what we've learned because you'll see when you take a look at my design document, you will see I changed a few things based off what we learned.

From that was.

Yeah, so that's, I'm pretty sure that's gonna change. So the requirements we got from the time, from that first kickoff meeting, very valuable. But from what we'd learned from the data, that had changed.

Yeah, I remember now.

Yeah, so yeah, I would say the design document should be the one. Yep. I'm actually looking at the course right now. It looks like our design document has a due date of December 1st. So it kind of gives you an estimate of kind of when to expect a design document from us. Or I don't know, maybe we can, but that would be that would be the final for grading. We can, well, maybe it's a conversation for the three of us to have, but maybe we can, I don't know, give them something.

I'd be happy to have your second draft or first draft or whatever. I'm going to stand up in front of the division on the 2nd and show off our fun new project. So that'd be very helpful.

Yeah, I think we could we could get something together. Yeah, no, that's more than honestly.

Awesome. I wasn't even thinking the full. designed, but I was thinking maybe next time we meet, it would be cool to talk about like a plan for making the design. Well, I guess I'm not exactly sure what the design document is, but I assumed it would be, the design would take longer than this next. So is this like an outline of the design that you have to finish in December or it's?

The design, it's the design, and that would be what... we get to work on for the next two terms. So right now, everything is like prototyping, playing with the project, understanding what the needs are. But for the next two terms, it's actually implementation.

Okay, got it.

Yeah, so yes, when we turn in on December, it's the thing. It's what we're going to work on.

Cool. Okay, I see.

And the design document will contain things like the project is composed of these major areas. And these major areas will work this way. And we will have like diagrams to show you what are the flows. So the things like the CCD speeds data, it goes to this service that picks up the data and then runs the clustering. And that service communicates with the thing that talks to the CNN. And then once we get the result, it will go to the data repository, which would be a database or, oh, by the way, we've discussed something. I don't know if you mentioned it, Troy, when I was not around, but we also were thinking about storing the cluster results in the FITS files themselves. So you would store the cluster information in the headers. So when you share that file, it's already there.

It's amazing.

Is that possible?

I think so.

To append the data.

Yeah.

It'll be, okay. I don't, I think that's totally fine. We typically did. If you figure that out, that's great. It feels kind of like an abuse of the header.

Yeah, it does. But imagine the scenario where, I don't know, you're sharing results with someone. And then you say, hey, the lab has this cool app that you just open the file there and it will just highlight all the clusters because the information is already in the fit file.

That's cool. Yeah. Okay, if that works, that's great. Otherwise, I think it. You could also, we just like store the Python data structures in a pickle file, or there's a few different ways to do that that are easy to open, which could be like a companion with the fits image file. But I don't have a strong opinion about that. So if you get it to fit in fits, that's cool. I kind of wonder if you're a lot, what will happen if you have like millions of lines of header, if it's still If that will crash other, if it's applications, or I don't.

Know, that's gonna be a test.

Yeah, I wonder, I wonder if this is used for astronomy, aren't they used to handle like a lot of data too?

Yeah, but I, maybe not in the header though, I don't, yeah, but yeah.

And that was an idea we had. Yeah, we'll see. Oh, going back to the design. So it will tell you what the functional areas are, the flows, how we're going to work, whether that's just

acquiring data and then turning in results and storing them. It will talk about the user interface and it will talk about the methods we use for getting the results. And that would have things like the software packages we use, whether we use OpenCV, whether we use NumPy or any other thing. And yeah, it's pretty much what we are going to do. And it's supposed to contain like the final project, but it's going to follow the agile methodology. So it's expected for things to kind of change.

Okay, yeah.

So it's not like, it's gonna be like, set in stone, but I mean, within constraints, right?

Okay, great. Yeah. Maybe, so you have like 2 weeks to finish that. Maybe we should meet again a week from now before Thanksgiving. yeah. Are you guys so in practice, you guys have to finish it before Thanksgiving? Are you working over the break?

I would be working over the break, I would think.

Yeah, I would do.

Thanks. We'll have. It'll be coming quick.

Okay. Well, yeah, so I'm happy to meet early next week or even later this week.

Appointment on next Monday. I have a thing.

What's that?

I have a thing next Monday. Am I on mute?

Oh, no, I heard you. Yeah, okay. At this time, the whole day or at this time, you mean?

It ends at 3.30, so I'm not sure if I can make it at 4.

I mean, yeah, I can do any time Monday or almost any time Tuesday.

I can do early Monday.

Yeah, it should be good anytime Monday.

You can do like 10.

Yeah, we could probably set something up in the morning.

Yeah, that works for me.

Okay, let's see that. And then is there anything, do you guys want any other input now as you plan the design? Or Or I can even chat again like Friday if that's useful. Well, I guess

Friday is basically Monday. But yeah, anyway, I realize you guys have a lot of pressure, so I'm happy to help this week or next.

I don't know, maybe, I don't really have anything right now. I don't know guys, but you think maybe, I don't know, maybe a search. Maybe emailing in between, sending a few messages with questions if we need to.

Yeah, and I think at the current point, if we, I think with our individual designs, if we combine them and maybe send them over for some input beforehand, because it'll be a little bit before we actually start on the implementation of it and before everything's ready. So it'd be good to get input when we have everything sort of planned out.

Okay. Okay, that sounds good. I'll be more responsive this week if you send emails. I don't know how much time you guys have. I was going to show you one other thing now if you're curious about the CNN.

I am.

Yeah.

Okay, so maybe you... You might have already found this, but okay, this is back in... It sounds like you guys found this MLCCD repo or group of repos. The main one lately is this MLCCD models. And if you look in notebooks, there's kind of some... Interesting cases. So I think the main CNN one is this Tridium recognition CNN. And this, by the way, you might have, I guess you've already realized the format of the data in this repo is not the FITS data. It's kind of a different structure that Emil made to hold the matrices. You made this class CCD data. Did you guys?

Yeah, I was going through that. It's.

Yeah, I mean, I think you guys should look offline at that, but that's, it's just a holder for matrices. So it's just, especially the simulated data, which I didn't send you, but sounds like you made some. That comes in that format. There's no magic in that.

Yeah, I was going to ask if that format is going to be used for other kinds of CCD experiments. Because in my design, actually talking about design, I have a data structure called CCD model data. No, it's called CCD model capture. which basically represents whatever comes from the FITS file. But the idea would be that it can represent raw data from a CCD, not necessarily coming from a FITS file. But if you guys have this data structure, it would be better for me to use that instead.

Yeah, I think it's probably better to not reinvent the wheel.

Yeah.

Yes, I'm sorry. But I yeah, I think also if it's also there's not much to the class. So if like you find there's some functionality that's missing that you want, we could either modify this class or make a separate class. It's not. There's not so much to it, but all basically the notebooks in this repository use this this format. But I would, I would say if you manage to figure it out, it's probably better to stick to this one just so you can then grab this code too.

Yeah, I'll just have to find a way to turn the cluster data from the fits just into that, just to feed it in. It would be a lot easier.

I think that's easier. The only, the funny thing about this format is that it And so instead of a two by two matrix, it's like a, so for yours are like 3200 by 550 pixels. It would be that, but there's a third dimension that's for like color. So like in real images that maybe you would have the pixel array, but in red, green, and blue.

Yeah.

In this case, there's no color. So like, for example, in the fits, it's It's just black, it's just like grayscale. So this format kind of preserves that red, green, blue, which is just like, so we end up taking just the zeroth element of that third dimension and it's kind of meaningless. Just so you know, if you see that, that's not.

Actually, actually, if you think about it, and this was a discussion we had in the previous meeting, and because of the dynamic range, it's so large. Right, you have these huge numbers. If you try to represent that in grayscale for the human eye to see, you end up losing information. The most we can represent in a display is 65,000 shades of gray. But if you use color, you have the whole spectrum. And if your display is like 24 bit or something, you have like 16 million colors. And that may be able to hold the whole range.

Yeah, so I would say if displaying it in color, that could be-- that's totally fine. And you're right. Maybe that's easier to span the range. Yeah, I just meant the underlying data itself is literally grayscale. So there's no need for three matrices. But for the display, it's definitely cool. Yeah, I mean, we use color for the display A lot.

I guess with that as well, it would just be like it would just be important that you could distinguish between energy levels and be able to relate that to something. I'm not sure how important, like how many significant figures we need to go out or maintain in that sort of data.

Right. I think for the display, it's like it's okay if it's rounded to 65,000 different levels. That's plenty. But it's still nice. I think, anyway, I agree in general, it's nice to look at it in color. It's kind of, the black and white are not very...

Yeah, it's just appealing. It's just candy for the human eye, right? So the actual numbers are the grayscale. And that's what you actually need to operate on. The other thing is just something for the human being.

Yep, I totally agree. Okay, cool. So that's the cloud. I can show you the class in a second. But I think you guys will just be able to understand it. But the way the model works. So this cell is just constructing or or setting the parameters for the this model from tensorflow. This is constructing it. And then this step is training it. And then you can, I don't know, do you guys have experience with like these Keras, Dave, machine learning models? I do not.

Neither do I, but I got a book that arrived last week. So yeah, I'm gonna delve into that because we're gonna need it.

Okay, yeah, I don't know exactly how it works, but it's not really complicated. Like you get, after you do the training, you can just save the resulting model.

Yeah, so that would be the weights, what you're storing here.

Yeah, the weights, exactly, Oh, okay. Yeah, exactly. You're showing the weights in this case. you're just doing this all in one notebook, but you might not always be, you don't always want to train it when you want to use it. But anyway, then this cell is how you actually evaluate the predictions. So then basically, you're feeding it a list of 10 by 10 clusters, and it gives you a list of scalar numbers between zero and one. And then I mean, the rest I think is just plotting stuff about that. But basically, I just wanted you to see how to kind of set up and train the neural network. In terms of lines of code, it's like not very much. Yeah, I'm impressed. Because it's all, it's all in TensorFlow.

Nice.

But, oh, you also mentioned the weights and biases thing, right, Troy?

Yeah.

Where did you run into that?

So when I went to the read me on that models page, because I was just going to get started and start running what it had.

Scroll all the way down.

Yeah, that's when it was create an account, log into Weights and Biases.

Yeah, so I think the read, so I don't think you really need this. It's just, yeah, it's in the read me, but see how far you can get without it.

Okay, yeah.

All right, I would say, don't just try to run every notebook, but I would say the interesting ones are this.

Yeah, I had read through that one. I was looking through, because there's a folder in there called data as well that has a link to like a Google Drive, I think, that has the training data that it used. But if Keras saves the weights and that's just reproducible within the notebooks without needing to train it or go through that, I guess, then it may not even be necessary to go through all that.

You mean if we just gave you the Keras file?

Yeah, as in just something to reproduce the model, then I wouldn't need to, because I'm... Especially at this point, I'm just trying to research it. I'm more interested in how it, what format it takes the cluster in, and then how it actually would classify it, and then what that output looks like. Because I don't think it's going to be part of our project to build a model or to build a new one. The work of it is mostly done. It does a good job at it. could be further training of it, but...

Never say never.

That is true.

Yeah, I agree. I think you're totally right, but I'm just thinking it will be, if we can decide, how we can decide if it's working well with your code if we don't. Well, I guess it's not. Yeah, let's think about that. But I also think we can provide you all of the data that it's using without much trouble. And you could run the training. I'll also see if we can just send you the saved weights. So, okay, we can try it both ways.

Yeah, and I can play around with it. And again, that's not urgent or anything right now. I'm more of just researching into it at the moment.

Okay, cool. But yeah, for now, I would look at okay, so the CCD data class I think is all mostly defined here. So you guys should read through this. There's not really much to say about it. The other, among the notebooks, not all of the notebooks are super interesting, but the I think compare models. This is the notebook that takes all the different models we train and compares this to the performance. This also might show you how to load the saved. Yeah, okay, good. This cell is loading all the saved models. And then so this is showing you how to load the weights and just execute the predictions without training. I wonder if these are actually stored here though.

No.

They're not.

That was the thing with a lot of the, especially the simulator, the Docker image was set with constants to Emil's system, all the folders he had set up. And it wasn't, it wasn't working too well for me, but I was able to get it going.

I wouldn't. Okay. Let me talk to Emil. I think I can get you those files, at least the trained models. That would be great. But for the simulation, I wouldn't worry too much about it now unless you're just having fun with it, but I don't think you have to figure that out. But yeah, the other ones I like, so there's the energy flow. This is this other network where it has similar performance as a CNN, but it doesn't have to take a fixed size matrix. Like you don't have to decide 10 by 10 or 12 by 12. You just give it like a set of pixels that can be any length. And you just give it the list of pixels above threshold.

Oh, okay.

So it's kind of more convenient for this data structure, I think.

I have a question. Yeah. so, can you scroll a bit up? So it seems that you guys are using CUDA, right? So if you're using that, I'm now wondering what kind of machine are we expecting this is going to run on?

Okay, so I think sometimes we use CUDA and we use the GPU, but not always. And to evaluate them, you definitely don't need it. I think Emil does this sometimes when he's training, like when he's doing kind of a hyper-perimeter scanner and he needs to train many, many times.

Yeah, because I ask because if we go back to our first meetings, we talked at some point of Mac OS laptop, and those do not have NVIDIA GPUs.

Sure, yeah. And all of this, so I don't know, this is maybe just a copy-paste remnant, but like this notebook doesn't rely on GPU at all. So, yeah, I mean, I guess this is just setting some environmental variable, but I don't think CUDA is actually used.

Because from there, you know, from there, we can also think of, so right now, for instance, what Troy is working on could be... could be like a separate service in the sense that it runs in a server where you have that kind of hardware and we can communicate from the application to that. Right. So we can, yeah, we can run things from that service that has that dedicated hardware. It runs faster for you and you can take all the advantages to one from that hardware.

That, I think that could be a cool extension. I would, I'm not sure we need that for like the baseline design. But if it's something, I mean, yeah, so I think if it's something you're

passionate about implementing, we could, that's something we could figure out. But for most of kind of the everyday use case, we don't need the GPU. Does that make sense?

Yeah, it's just throwing ideas. I'm just throwing ideas out, trying to think. Yeah, It's cool to think about these things.

Yeah, for sure. We use... We have a cluster here called Lawrencium. It's not exactly a supercomputer, but it's like, there's a lot of machines with GPUs, and so sometimes they'll be able to run stuff there. But yeah, the other one we use is the BDT. You've probably heard of this before, but this one just takes some high-level features from each cluster. So I think we give it basically, well, it's all kind of abstracted somewhere else, but there's this collection of data, X train BDT, that's like the energy and the sigma X and sigma Y for each cluster. So I think those are kind of the main interesting ones, the BDT, the CNN, the energy flow. and then compare models, which compares them all. I'm thinking that this prepare CCD data, what is this? No, I don't know. I thought we might have had a script to go from fits into this format, but I don't think that we do actually.

Okay, so it stores indices in an H5 file, looks like.

Yeah, so I mean the...

And then it just reads those. Okay.

Yeah, the CCD data class gets saved into an H5, I think. Or something or a pickle, but no, it's I'm actually not sure now. I think the clustered data gets saved in the H5s. No, but okay, sorry. The simulation is structured, the simulated data is structured a little bit differently than the actual data, where we don't simulate a whole exposure, we just simulate single interactions. And so each simulated event becomes one 10 by 10 matrix, as if you've already done the clustering. So that's actually kind of a big difference between the simulator format and the data format. It's like a, we skip the clustering step.

Yeah, it looks like it takes the metadata from the simulation in the H5 file and then it uses that to set the flags on it. Looking through it now.

Yeah, that's that sounds right.

That'll be something to look through.

Yeah.

All right. Did did anybody else have any other questions? I think we covered a lot.

Yeah, I'm good.

Really awesome stuff, guys. Really, really cool.

Yeah, very impressive. I kind of got the impression from emails before from your professor that it was like this semester, this quarter was just getting started and the real work was next two terms. But actually this seems like you guys are already working really hard.

Yeah, you've wasted no time getting down into the nitty-gritty to the point where I can't even contribute. So I'm happy to talk about it with the rest of the division though. I'll show them what you've been up to.

It's hot.

Thanks guys.

Thank.

You.

Thank you. We've been, we have been going pretty hard. They said the, they said the hello world version of your project and then we all had prototypes.

Wow, nice.

So we did a little something. That's cool. I appreciate you guys taking the time to meet with us tonight though. Absolutely on my side.

Alrighty.

All right. I will set up that meeting for Monday morning. I'll send out an e-mail probably tomorrow with the invite link.

Sounds great.

Yeah.

See you then. All right. Thanks guys.

Thank you.

Bye bye. Bye.
