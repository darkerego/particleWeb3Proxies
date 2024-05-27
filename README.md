# particleProxies

### Note: this code is totally unecessary.

<p>

Try this instead: 

https://gist.github.com/darkerego/7180cb6808a2bb30dfa5d9357e1afdc9

</p>



### About 
<p>
I love Particle.Network:


[https://particle.network](https://particle.network) 

They are amazing. It is not very difficult to 
modify most of my code to use particle as my web3 RPC, but sometimes it can be. So 
I decided to just write a script that creates a proxy listening 
on my local host for every chain that particle supports. This way 
I only need to update my RPC endpoint for my HTTPProvider and everything 
just kind of works.
</p>

### What's Next

<p>
It occured to me that I wrote this like an idiot. I think I will refractor it so that there is only one port listening on the localhost, and then you can just specify a path. Like:

- http://127.0.0.1:8545/ethereum
- http://127.0.0.1:8545/arbitrum

  Etc. Then just proxy the request to appropiate endpoint. 

</p>


### Setup
<p>
Just grab an API keypair:

[from here](https://dashboard.particle.network/#/applications)

and copy 
`env.example` to `.env` , update your `PROJECT_ID` and `PROJECT_SERVER_KEY`, and you are done!
</p>

[![asciicast](https://asciinema.org/a/658425.svg)](https://asciinema.org/a/658425)


### Did this help you?
<p>
Cause I love tips: 0xCe8406fCCD474637242a1112D33F6749c5e4772F
</p>

### Invite Code for Particle Drop:

(8BHMPJ)[https://pioneer.particle.network?inviteCode=8BHMPJ]
