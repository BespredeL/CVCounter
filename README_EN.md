## <div align="center">CVCounter</div>
This solution is far from ideal, probably just a piece of ..., but it works =)<br> 
This is my first experience working with Python, so it turned out the way it did.

This solution implements 2 types of views:

1. **Main view** - a page displaying the counter values and a video with recognition results
2. **Text view** - a page displaying only the counter values
3. **Text view with two counters** - a page on which the value of 2 counters is displayed (for example, at the input and output)

After several options, I decided to implement it with Flask, i.e. as a mini website solution, 
as it allows to avoid installing any additional software on the clients. 
Moreover, this solution is not resource-intensive for clients (except for the main view with video)

I managed to run 5 simultaneous counts (without video output), and 4 counts with video output.

Server specifications:

AMD Ryzen 5 3600
- GeForce GTX 1050 Ti (4GB)
- All main settings are located in the config.json file (rename config.json.example to config.json)

P.S.:
- Friends, if you don't mind, please don't remove my copyright at the bottom of the page. It's not a requirement, but if you leave it, I'll be very grateful to you!
- All of this was implemented without any specifications and nobody believed in success, so there is currently some chaos, but I will try to redo everything more correctly =)
- If this solution helped you, you can sponsor me by sending the word "Thanks". Contact details are below =))
- If you need help with the implementation, we can discuss it =).

## <div align="center">Screenshots</div>
<img src="https://github.com/BespredeL/BespredeL/blob/c27b6d786e6569cbaa17d49eac8c7433812a1024/Desktop-2023.12.31-13.16.42.01.gif" alt="" width="360">
<img src="https://github.com/BespredeL/BespredeL/blob/c27b6d786e6569cbaa17d49eac8c7433812a1024/Main%20View.png" alt="" width="360">
<img src="https://github.com/BespredeL/BespredeL/blob/c27b6d786e6569cbaa17d49eac8c7433812a1024/Text%20View.png" alt="" width="360">

## <div align="center">Author</div>

Alexander Kireev

Website: [https://bespredel.name](https://bespredel.name)<br>
E-mail: [hello@bespredel.name](mailto:hello@bespredel.name)<br>
Telegram: [https://t.me/BespredeL_name](https://t.me/BespredeL_name)

## <div align="center">References</div>
Ultralytics: [https://github.com/ultralytics](https://github.com/ultralytics)

## <div align="center">License</div>
**AGPL-3.0 License**: This [OSI-approved](https://opensource.org/licenses/) open-source license is ideal for students and enthusiasts,
  promoting open collaboration and knowledge sharing.