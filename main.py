import pygame, math, os

pygame.init()
WINDOW = pygame.display.set_mode((900, 500))
pygame.display.set_caption("Rocket Simulation")



#----------------------------------ROCKET COMPONENTS------------------------------------

class Engine:
  def __init__(self, name, time, thrustSL = 0, thrustV = 0):
    self.name = name
    self.thrustSL = thrustSL #unit: kN
    self.thrustV = thrustV #unit: kN
    self.burnTime = time #unit: s
    self.fire = False
    
  def run(self, alt):
    self.fire = True
    if alt <= 100000:
      self.burnTime -= 1.0 / 20
      return self.thrustSL
    elif alt > 100000:
      self.burnTime -= 1.0 / 20
      return self.thrustV
    else:
      return 0
    
  def shutDown(self):
    self.burnTime = -1
    self.thrustSL = 0.0
    self.thrustV = 0.0
    self.fire = False

class Stage:
  def __init__(self, emptyMass = 0, grossMass = 0, eng1 = Engine(None, -1), eng1Count = 0, hotSeparation = False, eng2 = Engine(None, -1), eng2Count = 0): 
    self.emptyMass = emptyMass
    self.mass = grossMass
    self.eng1 = eng1
    self.eng1Count = eng1Count
    self.eng2 = eng2
    self.eng2Count = eng2Count
    self.hotSeparation = hotSeparation    
    self.runHotSeparation = False
    if self.eng2Count == 0 and self.eng1.burnTime != 0:
      self.eng1FuelConsumption = (self.mass - self.emptyMass) / self.eng1.burnTime / 20
      self.eng2FuelConsumption = 0
    elif self.eng2Count != 0 and self.eng1.burnTime != 0:
      minTime = min(self.eng1.burnTime, self.eng2.burnTime)
      maxTime = max(self.eng1.burnTime, self.eng2.burnTime)
      self.eng1FuelConsumption = (self.mass - self.emptyMass) / (2 * minTime + maxTime - minTime) / 20
      self.eng2FuelConsumption = self.eng1FuelConsumption #units: kg/s
    else:
      self.eng1FuelConsumption = self.eng2FuelConsumption = 0
    self.fireStage = False
    self.readySeparate = False
    self.separateTimer = 0.0

  def ignition(self, alt):
    thrust = 0
    if self.eng1.burnTime != -1: thrust += self.eng1.run(alt) * self.eng1Count
    if self.eng2.burnTime != -1 and self.eng2Count != 0: thrust += self.eng2.run(alt) * self.eng2Count
    return thrust
  
  def separate(self):
    self.mass = 0
    self.eng1.shutDown()
    self.eng2.shutDown()
    self.eng1FuelConsumption = 0
    self.eng2FuelConsumption = 0

class Payload:
  def __init__(self, name, mass):
    self.name = name
    self.mass = mass #unit: kg

class LaunchEscapeTower:
  def __init__(self, mass = 0):
    self.mass = mass #unit: kg
    
  def separate(self):
    self.mass = 0

class Fairing:
  def __init__(self, mass):
    self.mass = mass #unit: kg

  def separate(self):
    self.mass = 0

class Rocket:
  def __init__(self, name, firstStage, fairing, payload, secondStage = Stage(0), booster = Stage(0), thirdStage = Stage(0), launchEscape = LaunchEscapeTower(0)):
    self.name = name
    self.formattedName = ""
    for char in self.name:
      if char.isalpha() or (ord(char) >= 48 and ord(char) <= 57):
        self.formattedName += char
    self.formattedName = self.formattedName.lower()
    self.boosters = booster
    self.firstStage = firstStage
    self.secondStage = secondStage
    self.thirdStage = thirdStage
    self.payload = payload
    self.launchEscape = launchEscape
    self.fairing = fairing
    self.totalBurnTime = max(self.firstStage.eng1.burnTime, self.firstStage.eng2.burnTime) + max(self.secondStage.eng1.burnTime, self.secondStage.eng2.burnTime) + max(self.thirdStage.eng1.burnTime, self.thirdStage.eng2.burnTime)
    self.correctionRange = 30000.0 #unit: m
    self.stopFlight = False
    self.AOA = 90.0 #unit: degrees
    self.orbits = {'LEO': 200000.0, 
                   'SSO': 700000.0, 
                   'GTO': 37000000.0} #units: m
    self.orbit = 'LEO' #low-Earth orbit by default
  
  def canLiftOff(self, mass):
    return (self.Fg(mass, 0.0)) < ((self.firstStage.ignition(0) + self.boosters.ignition(0)) * 1000)
  
  def evaluateStatus(self):
    #order of status code: first stage, first stage engines, boosters, booster engines, second stage... launch escape tower, fairing
    #0 -> module doesn't exists; 1 -> module exists; 2 -> engine is not running; 3 -> engine is running
    status = ""
    if self.firstStage.mass != 0.0:
      status += "1"
      if self.firstStage.eng1.fire:
        status += "3"
      else:
        status += "2"
      if self.firstStage.eng2.fire:
        status += "3"
      else:
        status += "2"
    else:
      status += "022"
    if self.boosters.mass != 0.0:
      status += "1"
      if self.boosters.eng1.fire:
        status += "3"
      else:
        status += "2"
      if self.boosters.eng2.fire:
        status += "3"
      else:
        status += "2"
    else:
      status += "022"
    if self.secondStage.mass != 0.0:
      status += "1"
      if self.secondStage.eng1.fire:
        status += "3"
      else:
        status += "2"
      if self.secondStage.eng2.fire:
        status += "3"
      else:
        status += "2"
    else:
      status += "022"
    if self.thirdStage.mass != 0.0:
      status += "1"
      if self.thirdStage.eng1.fire:
        status += "3"
      else:
        status += "2"
      if self.thirdStage.eng2.fire:
        status += "3"
      else:
        status += "2"
    else:
      status += "022"
    if self.launchEscape.mass != 0.0:
      status += "1"
    else:
      status += "0"
    if self.fairing.mass != 0.0:
      status += "1"
    else:
      status += "0"

    return status
    
  def evaluateResult(self, alt, vNet): 
    vNet += 460
    desiredVelocity = math.sqrt((6.67 * (10 ** -11) * 5.97219 * (10 ** 24)) / (6378000 + alt)) #unit: m/s 
    if alt > self.orbits[self.orbit] - self.correctionRange and alt < self.orbits[self.orbit] + self.correctionRange:
      if vNet > desiredVelocity - 480 and vNet < desiredVelocity + 480:
        return [f"Orbital altitude: {(alt / 1000):.4f} km", f"Orbital velocity: {vNet:.4f} m/s", f"Desired velocity: {desiredVelocity:.4f} m/s", f"Result: The launch into LEO was successful and its accuracy was fairly high."]
      elif vNet > desiredVelocity + 480:
        return [f"Orbital altitude: {(alt / 1000):.4f} km", f"Orbital velocity: {vNet:.4f} m/s", f"Desired velocity: {desiredVelocity:.4f} m/s", f"Result: The launch into LEO was successful. The satellite/module/ship's velocity is considerably higher than desired, thus further velocity adjustments may need to be performed to reduce the centrifugal force."]
      elif vNet < desiredVelocity - 480:
        return [f"Orbital altitude: {(alt / 1000):.4f} km", f"Orbital velocity: {vNet:.4f} m/s", f"Desired velocity: {desiredVelocity:.4f}", f"Result: The launch into LEO was a partial-success. The satellite/module/ship's velocity is considerably lower than desired and its altitude may continue to drop. Further adjustments are needed to increase the centrifugal force."]
    else:
      if alt > self.orbits["LEO"] + self.correctionRange:
        return [f"Orbital altitude: {(alt / 1000):.4f} km", f"Orbital velocity: {vNet:.4f} m/s", f"Desired altitude: {int(self.orbits[self.orbit] / 1000)} km", f"Result: The launch was a partial-success. The altitude acquired is considerably higher than the desired altitude, thus the satellite/module/ship may need to perform adjustments to raise its altitude."]
      elif alt > self.orbits["LEO"] - 7000:
        return [f"Orbital altitude: {(alt / 1000):.4f} km", f"Orbital velocity: {vNet:.4f} m/s", f"Desired altitude: {int(self.orbits[self.orbit] / 1000)} km", f"Result: The launch was a partial-success. The altitude acquired is considerably lower than the desired altitude, thus the satellite/module/ship may need to perform adjustments to raise its altitude."]
      else:
        return [f"Orbital altitude: {(alt / 1000):.4f} km", f"Orbital velocity: {vNet:.4f} m/s", f"Desired altitude: {int(self.orbits[self.orbit] / 1000)} km", f"Result: The launch had failed. The acquired altitude is unacceptably lower than the desired altitude."]
    
  def Fg(self, mass, alt):
    return ((6.67 * (10 ** -11)) * mass * (5.97219 * (10 ** 24))) / (((6378000 + alt) * (6378000 + alt)))

  def Fc(self, mass, v, alt):
    return mass * ((v + 460) ** 2) / (6378000 + alt)
  
  def rocketMass(self):
    return self.boosters.mass + self.firstStage.mass + self.secondStage.mass + self.thirdStage.mass + self.payload.mass + self.launchEscape.mass + self.fairing.mass

  def lift(self):
    pass

  def drag(self):
    pass

  def findAcceleration(self, thrust, alt, mass, v):
    Nx = math.cos(self.AOA * math.pi / 180) * thrust * 1000 #units: N
    Ny = math.sin(self.AOA * math.pi / 180) * thrust * 1000 #units: N
    Ny = Ny + (-1.0 * self.Fg(mass, alt)) + self.Fc(mass, v, alt)
    ax = Nx / mass #units: m/s²
    ay = Ny / mass #units: m/s²
    aNet = math.sqrt(ax * ax + ay * ay)
    return aNet, ay, ax

  def executeFlightPath(self, t, alt, baseRate): 
    if t > 7 and self.AOA >= 0.5 and alt < self.orbits["LEO"] * 0.4:
      self.AOA -= 2 * baseRate
    elif t > 7 and self.AOA >= 0.5 and alt > self.orbits["LEO"] * 0.4 and alt < self.orbits["LEO"] - self.correctionRange:
      self.AOA -= baseRate



#-----------------------------------ROCKET LIBRARY-----------------------------------

#CZ-5B:
YF100 = Engine("YF-100", 173, 1223.5, 1339.48) #units: kN, s
YF77 = Engine("YF-77", 487, 560, 700) #units: kN, s
CZ5BBoosters = Stage(55200, 626400, YF100, 8) #units: kg
CZ5BFirstStage = Stage(21600, 186900, YF77, 2) #units: kg
CZ5BFairing = Fairing(12700)
CSSMengtian = Payload("CSS Mengtian", 23000)
CZ5B = Rocket("CZ-5B", CZ5BFirstStage, CZ5BFairing, CSSMengtian, Stage(), CZ5BBoosters)

#CZ-5C (arbituary):
YF130 = Engine("YF-130", 480, 4800, 5200) #arbituary
CZ5CFirstStage = Stage(27600, 500000, YF130, 2) #arbituary
CSSExperimentModuleIII = Payload("CSS Experiment Module III", 25000) #arbituary
CZ5C = Rocket("CZ-5C", CZ5CFirstStage, CZ5BFairing, CSSExperimentModuleIII) #arbituary

#Brick (for fun):
BrickFirstStage = Stage(27600, 500000, YF130, 8)
BabyBrick = Payload("Baby Brick", 25000)
Brick = Rocket("Brick", BrickFirstStage, CZ5BFairing, BabyBrick)

#Soyuz 2.1a:
RD107A = Engine("RD-107A", 118, 839.48, 1019.93)
RD108A = Engine("RD-108A", 286, 792.41, 921.86)
RD0110 = Engine("RD-0110", 239, 298, 298)
Soyuz21aBoosters = Stage(15136, 177852, RD107A, 4)
Soyuz21aFirstStage = Stage(6545, 99765, RD108A, 1, True)
Soyuz21aSecondStage = Stage(2355, 27755, RD0110, 1)
Soyuz21aLaunchEscapeTower = LaunchEscapeTower(2000)
Soyuz21aFairing = Fairing(4300)
SoyuzMS23 = Payload("Soyuz MS-23", 7080)
Soyuz21a = Rocket("Soyuz 2.1a", Soyuz21aFirstStage, Soyuz21aFairing, SoyuzMS23, Soyuz21aSecondStage, Soyuz21aBoosters, Stage(), Soyuz21aLaunchEscapeTower)



#----------------------------------UI AND MAIN LOOP----------------------------------

BLUE = (0, 5, 70)
WHITE = (255, 255, 255)
GREEN = (0, 90, 0)
BRIGHTGREEN = (170, 255, 0)
YELLOW = (255, 255, 0)

DATAFONT = pygame.font.SysFont("couriernew", 13, True)
EVENTLOGFONT = pygame.font.SysFont("couriernew", 13, True)
NAMEFONT = pygame.font.SysFont("couriernew", 35, True, True)

ASSESTSPATH = os.path.abspath(os.getcwd()) + "/Assets/" #"B:/HuangJiaQi/Python/Rocket Simulation Pygame/Assets/"
ROCKETSPATH = os.path.abspath(os.getcwd()) + "/Rockets/" #"B:/HuangJiaQi/Python/Rocket Simulation Pygame/Rockets/"

class EventLog:
  def __init__(self, message):
    self.message = message
  
  def displayEvent(self, yCoordinate):
    eventLogText = EVENTLOGFONT.render(self.message, 1, YELLOW)
    WINDOW.blit(eventLogText, (0.975 * WINDOW.get_width() - eventLogText.get_width(), yCoordinate))

class Button:
  def __init__(self, imageDirectory, x, y, scale):
    self.image = pygame.image.load(imageDirectory)
    width = self.image.get_width()
    height = self.image.get_height()
    self.image = pygame.transform.scale(self.image, (int(width * scale), int(height * scale)))
    self.button = self.image.get_rect()
    self.button.center = (x, y)
    self.clicked = False

  def createButton(self):
    WINDOW.blit(self.image, (self.button.x, self.button.y))

  def isClicked(self):
    mousePos = pygame.mouse.get_pos()
    if self.button.collidepoint(mousePos):
      if pygame.mouse.get_pressed()[0] == 1 and not self.clicked:
        self.clicked = True
        return True
    if pygame.mouse.get_pressed()[0] == 0:
      self.clicked = False
 
    return False

LAUNCHBUTTON = Button(f"{ASSESTSPATH}launch.png", (WINDOW.get_width() / 2 - 140), (WINDOW.get_height() / 2), 0.6)
BUILDBUTTON = Button(f"{ASSESTSPATH}build.png", (WINDOW.get_width() / 2 + 140), (WINDOW.get_height() / 2), 0.6)
LEOBUTTON = Button(f"{ASSESTSPATH}leo.png", (WINDOW.get_width() / 2 - 200), (WINDOW.get_height() / 2), 0.6)
GTOBUTTON = Button(f"{ASSESTSPATH}gto.png", (WINDOW.get_width() / 2), (WINDOW.get_height() / 2), 0.6)
SSOBUTTON = Button(f"{ASSESTSPATH}sso.png", (WINDOW.get_width() / 2 + 200), (WINDOW.get_height() / 2), 0.6)

SOYUZ21ABUTTON = Button(f"{ASSESTSPATH}soyuz21a.png", (WINDOW.get_width() * 0.1), 60, 0.6)
CZ5BBUTTON = Button(f"{ASSESTSPATH}cz5b.png", (WINDOW.get_width() * 0.1), 140, 0.6)
BRICKBUTTON = Button(f"{ASSESTSPATH}brick.png", (WINDOW.get_width() * 0.1), 220, 0.6)

def drawGreenBackground():
  WINDOW.fill(GREEN)
  #pygame.display.update()

def drawBlueBackground():
  WINDOW.fill(BLUE)
  #pygame.display.update()

def drawStartScreen():
  drawGreenBackground()
  LAUNCHBUTTON.createButton()
  BUILDBUTTON.createButton()
  if LAUNCHBUTTON.isClicked(): return "select rocket"
  if BUILDBUTTON.isClicked(): return "build rocket"
  return "start screen"

def drawEndScreen(obj, alt, vNet):
  initialHeight = 0.04 * WINDOW.get_height()
  xCoordinate = 0.025 * WINDOW.get_width()
  decreaseHeight = 20
  keys = pygame.key.get_pressed()
  if keys[pygame.K_ESCAPE]: return "start screen"
  try:
    wallpaper = pygame.image.load(f"{ASSESTSPATH}{obj.formattedName}_wallpaper.png")
    WINDOW.blit(wallpaper, (0, 0))
  except FileNotFoundError:
    wallpaper = pygame.image.load(f"{ASSESTSPATH}soyuz21a_wallpaper.png")
    WINDOW.blit(wallpaper, (0, 0))
  for index, value in enumerate(obj.evaluateResult(alt, vNet)):
    text = DATAFONT.render(value, 1, YELLOW)
    WINDOW.blit(text, (xCoordinate, initialHeight + (index * decreaseHeight)))
  return "end screen"

def printData(t, obj, mass, aNet, ax, ay, vNet, vx, vy, altitude, thrust, throttle):
  initialHeight = 0.04 * WINDOW.get_height()
  xCoordinate = 0.025 * WINDOW.get_width()
  decreaseHeight = 20
  stages = [obj.boosters, obj.firstStage, obj.secondStage, obj.thirdStage]
  runningEngines = ""

  timeText = DATAFONT.render("Time: %.2f s" % t, 1, BRIGHTGREEN)
  aoaText = DATAFONT.render("AOA: %.4f deg" % obj.AOA, 1, BRIGHTGREEN)
  massText = DATAFONT.render("Mass: %.4f kg" % mass, 1, BRIGHTGREEN)
  generalBlock = [timeText, aoaText, massText]
  for index, value in enumerate(generalBlock):
    WINDOW.blit(value, (xCoordinate, initialHeight + (index * decreaseHeight)))
    if index == len(generalBlock) - 1:
      initialHeight += (index * decreaseHeight) + 50
  
  altText = DATAFONT.render("Altitude: %.4f m" % altitude, 1, BRIGHTGREEN)
  altitudeBlock = [altText]
  for index, value in enumerate(altitudeBlock):
    WINDOW.blit(value, (xCoordinate, initialHeight + (index * decreaseHeight)))
    if index == len(altitudeBlock) - 1:
      initialHeight += (index * decreaseHeight) + 50

  aNetText = DATAFONT.render("Acceleration: %.4f m/s²" % aNet, 1, BRIGHTGREEN)
  axText = DATAFONT.render("Horizontal acceleration: %.4f m/s²" % ax, 1, BRIGHTGREEN)
  ayText = DATAFONT.render("Vertical acceleration: %.4f m/s²" % ay, 1, BRIGHTGREEN)
  accelerationBlock = [aNetText, axText, ayText]
  for index, value in enumerate(accelerationBlock):
    WINDOW.blit(value, (xCoordinate, initialHeight + (index * decreaseHeight)))
    if index == len(accelerationBlock) - 1:
      initialHeight += (index * decreaseHeight) + 50

  vNetText = DATAFONT.render("Velocity: %.4f m/s (%.4f km/h)" % (vNet, (vNet * 3.6)), 1, BRIGHTGREEN)
  vxText = DATAFONT.render("Horizontal velocity: %.4f m/s" % vx, 1, BRIGHTGREEN)
  vyText = DATAFONT.render("Vertical velocity: %.4f m/s" % vy, 1, BRIGHTGREEN)
  velocityBlock = [vNetText, vxText, vyText]
  for index, value in enumerate(velocityBlock):
    WINDOW.blit(value, (xCoordinate, initialHeight + (index * decreaseHeight)))
    if index == len(velocityBlock) - 1:
      initialHeight += (index * decreaseHeight) + 50

  for index, stage in enumerate(stages):
    if stage.mass != 0:
      if stage.fireStage:
        if stage.eng1.burnTime != -1:
          runningEngines += "%s x %s, " % (stage.eng1Count, stage.eng1.name)
        if stage.eng2Count != 0 and stage.eng2.burnTime != -1:
          runningEngines += "%s x %s, " % (stage.eng2Count, stage.eng2.name)
      if stage.runHotSeparation:
        runningEngines += "%s x %s, " % (stages[index + 1].eng1Count, stages[index + 1].eng1.name)
        if stages[index + 1].eng2Count != 0 and stages[index + 1].eng2.burnTime != -1:
          runningEngines += "%s x %s, " % (stages[index + 1].eng2Count, stages[index + 1].eng2.name)
  if len(runningEngines) > 2:
    runningEngines = runningEngines[:-2] #this deletes the comma and the space at the very end of the text
  thrustText = DATAFONT.render("Thrust: %.4f kN" % thrust, 1, BRIGHTGREEN)
  runningEnginesText = DATAFONT.render("Running: %s" % runningEngines, 1, BRIGHTGREEN)
  throttleText = DATAFONT.render(f"Throttle: {(throttle * 100):.0f}%", 1, BRIGHTGREEN)
  thrustBlock = [thrustText, throttleText, runningEnginesText]
  for index, value in enumerate(thrustBlock):
    WINDOW.blit(value, (xCoordinate, initialHeight + (index * decreaseHeight)))

  nameText = NAMEFONT.render(obj.name, 1, BRIGHTGREEN)
  WINDOW.blit(nameText, (WINDOW.get_width() - xCoordinate - nameText.get_width(), 0.04 * WINDOW.get_height()))

  targetOrbitText = DATAFONT.render(f"{str(int(int(obj.orbits[obj.orbit]) / 1000))} km {obj.orbit}", 1, BRIGHTGREEN)
  payloadText = DATAFONT.render(f"{obj.payload.name}", 1, BRIGHTGREEN)
  objectiveBlock = [targetOrbitText, payloadText]
  for index, value in enumerate(objectiveBlock):
    WINDOW.blit(value, (WINDOW.get_width() - xCoordinate - value.get_width(), 0.04 * WINDOW.get_height() + (nameText.get_height() / 2) + ((index + 1) * decreaseHeight)))

def addEventLog(queueList, queueTime, message):
  queueTime.append(120)
  queueList.append(EventLog(message))

def printEventLog(queueList, queueTime):
  if len(queueTime) != 0:
    for index, value in enumerate(queueTime):
      if value == 0:
        queueList.pop(index)
        queueTime.pop(index)
      else:
        queueList[index].displayEvent(150 + 20 * index)
        queueTime[index] = value - 1

def displayModel(obj, usedModels):
  modelName = obj.formattedName + "_" + obj.evaluateStatus()
  if os.path.exists(f"{ROCKETSPATH}{obj.formattedName}"):
    if os.path.exists(f"{ROCKETSPATH}{obj.formattedName}/{modelName}.png"):
      rawModel = pygame.image.load(f"{ROCKETSPATH}{obj.formattedName}/{modelName}.png")
      model = pygame.transform.scale(rawModel, (rawModel.get_width() * 0.9, rawModel.get_height() * 0.9))
      model = pygame.transform.rotate(model, (90.0 - obj.AOA))
      WINDOW.blit(model, (400, WINDOW.get_height() * 0.03))
      if modelName not in usedModels:
        usedModels.append(modelName)
    else:
      try:
        rawModel = pygame.image.load(f"{ROCKETSPATH}{obj.formattedName}/{usedModels[-1]}.png")
        model = pygame.transform.rotate(rawModel, (90.0 - obj.AOA))
        WINDOW.blit(model, (400, WINDOW.get_height() * 0.03))
      except IndexError:
        #Shouldn't happen, but if so it would just not add a model
        return
  else:
    #Then just use the generic model
    pass

def main():
  frames = pygame.time.Clock()
  programState = "start screen"
  run = True

  while run:
    frames.tick(20)
    for event in pygame.event.get():
      if event.type == pygame.QUIT:
        run = False
    if pygame.key.get_pressed()[pygame.K_ESCAPE]: programState = "start screen"

    if programState == "start screen":
      programState = drawStartScreen()

    if programState == "select rocket":
      t = altitude = thrust = velocity = yVelocity = xVelocity = acceleration = launchCompleteTimer = 0.0
      payloadDeployed = False
      thrustMultiplier = 1.0
      queueList, queueTime, usedModels = [], [], []
      drawBlueBackground()
      SOYUZ21ABUTTON.createButton()
      CZ5BBUTTON.createButton()
      BRICKBUTTON.createButton()
      if SOYUZ21ABUTTON.isClicked():
        rocket = Soyuz21a
        mass = rocket.rocketMass()
        baseRate = 90 / (max(rocket.firstStage.eng1.burnTime, rocket.firstStage.eng2.burnTime) + max(rocket.secondStage.eng1.burnTime, rocket.secondStage.eng2.burnTime) + max(rocket.thirdStage.eng1.burnTime, rocket.thirdStage.eng2.burnTime) - 7) / 20.0
        programState = "select orbit" 
      if CZ5BBUTTON.isClicked():
        rocket = CZ5B
        baseRate = 90 / (max(rocket.firstStage.eng1.burnTime, rocket.firstStage.eng2.burnTime) + max(rocket.secondStage.eng1.burnTime, rocket.secondStage.eng2.burnTime) + max(rocket.thirdStage.eng1.burnTime, rocket.thirdStage.eng2.burnTime) - 7) / 20.0
        programState = "select orbit" 
      if BRICKBUTTON.isClicked():
        rocket = Brick
        baseRate = 90 / (max(rocket.firstStage.eng1.burnTime, rocket.firstStage.eng2.burnTime) + max(rocket.secondStage.eng1.burnTime, rocket.secondStage.eng2.burnTime) + max(rocket.thirdStage.eng1.burnTime, rocket.thirdStage.eng2.burnTime) - 7) / 20.0
        programState = "select orbit" 
    
    if programState == "select orbit":
      drawBlueBackground()
      LEOBUTTON.createButton()
      GTOBUTTON.createButton()
      SSOBUTTON.createButton()
      if LEOBUTTON.isClicked():
        rocket.firstStage.fireStage = True
        rocket.boosters.fireStage = True
        rocket.orbit = 'LEO'
        programState = "lift-off"
      if GTOBUTTON.isClicked():
        rocket.firstStage.fireStage = True
        rocket.boosters.fireStage = True
        rocket.orbit = 'GTO'
        programState = "lift-off"
      if SSOBUTTON.isClicked():
        rocket.firstStage.fireStage = True
        rocket.boosters.fireStage = True
        rocket.orbit = 'SSO'
        programState = "lift-off"

    if programState == "build rocket":
      #Add
      programState = "start screen"
      #if not rocket.canLiftOff(mass):
        #print("Not enough thrust, unable to lift-off.")
        
    if programState == "lift-off":
      t += 1.0 / 20 #basis of time is 1 / 20 seconds
      rocket.executeFlightPath(t, altitude, baseRate)

      keys = pygame.key.get_pressed()
      if keys[pygame.K_UP] and rocket.AOA <= 90.0 and t >= 7.0 and not payloadDeployed: rocket.AOA += 0.1
      if keys[pygame.K_DOWN] and t >= 7.0 and not payloadDeployed: rocket.AOA -= 0.1
      if keys[pygame.K_LSHIFT] and thrustMultiplier < 1.0: thrustMultiplier += 0.01
      if keys[pygame.K_LCTRL] and thrustMultiplier > 0.7: thrustMultiplier -= 0.01

      #Separations:
      if rocket.boosters.readySeparate:
        rocket.boosters.separateTimer += 1
        if rocket.boosters.separateTimer == 20:
          rocket.boosters.separate()
          addEventLog(queueList, queueTime, "Boosters separation")
          rocket.boosters.readySeparate = False
      if rocket.firstStage.readySeparate:
        rocket.firstStage.separateTimer += 1
        if rocket.firstStage.separateTimer == 20:
          rocket.firstStage.separate()
          addEventLog(queueList, queueTime, "Stage one separation")
          rocket.firstStage.readySeparate = False
      if rocket.secondStage.readySeparate:
        rocket.secondStage.separateTimer += 1
        if rocket.secondStage.separateTimer == 20:
          rocket.secondStage.separate()
          addEventLog(queueList, queueTime, "Stage two separation")
          rocket.secondStage.readySeparate = False
      if altitude >= 69000 and rocket.launchEscape.mass != 0: 
        rocket.launchEscape.separate() 
        addEventLog(queueList, queueTime, "Launch-escape tower jettisoned")
      if altitude >= 130000 and rocket.fairing.mass != 0:
        rocket.fairing.separate()
        addEventLog(queueList, queueTime, "Fairing jettisoned")

      #Stage one and booster activities:
      if max(rocket.firstStage.eng1.burnTime, rocket.firstStage.eng2.burnTime) > 0 and rocket.firstStage.fireStage: #run first stage and boosters
        thrust = (rocket.firstStage.ignition(altitude) + rocket.boosters.ignition(altitude)) * thrustMultiplier
        rocket.firstStage.mass = rocket.firstStage.mass - (rocket.firstStage.eng1FuelConsumption + rocket.firstStage.eng2FuelConsumption)
        rocket.boosters.mass = rocket.boosters.mass - (rocket.boosters.eng1FuelConsumption + rocket.boosters.eng2FuelConsumption)
        if (max(rocket.boosters.eng1.burnTime, rocket.boosters.eng2.burnTime) <= 0 and max(rocket.boosters.eng1.burnTime, rocket.boosters.eng2.burnTime) > -1.0) and rocket.boosters.eng1Count != 0.0: 
          rocket.boosters.eng1.shutDown()
          rocket.boosters.eng2.shutDown()
          rocket.boosters.eng1FuelConsumption = 0
          rocket.boosters.eng2FuelConsumption = 0
          rocket.boosters.fireStage = False
          rocket.boosters.readySeparate = True
          addEventLog(queueList, queueTime, "Boosters shut down")
        if rocket.firstStage.eng2Count != 0 and (rocket.firstStage.eng2.burnTime <= 0 and rocket.firstStage.eng2.burnTime > -1.0):
          rocket.firstStage.eng2.shutDown()
          rocket.firstStage.eng2FuelConsumption = 0
          addEventLog(queueList, queueTime, "Stage one secondary engine shut down")
        if rocket.firstStage.eng1.burnTime <= 0 and rocket.firstStage.eng1.burnTime > -1.0:
          rocket.firstStage.eng1.shutDown()
          rocket.firstStage.eng1FuelConsumption = 0
          addEventLog(queueList, queueTime, "Stage one main engine shut down")
        if rocket.firstStage.hotSeparation and (rocket.firstStage.eng1.burnTime <= 2.0 and rocket.firstStage.eng1.burnTime >= 1.5) and not rocket.firstStage.runHotSeparation:
          addEventLog(queueList, queueTime, "Stage two ignition")
          rocket.firstStage.runHotSeparation = True
        if rocket.firstStage.runHotSeparation:
          thrust += rocket.secondStage.ignition(altitude)
          rocket.secondStage.mass = rocket.secondStage.mass - (rocket.secondStage.eng1FuelConsumption + rocket.secondStage.eng2FuelConsumption)
        if rocket.firstStage.eng1.burnTime == -1 and rocket.firstStage.eng2.burnTime == -1:
          rocket.firstStage.readySeparate = True
          rocket.firstStage.fireStage = False
          if rocket.secondStage.eng1Count != 0:
            rocket.secondStage.fireStage = True
            if not rocket.firstStage.hotSeparation:
              addEventLog(queueList, queueTime, "Stage two ignition")
      
      #Stage two activities:
      if max(rocket.secondStage.eng1.burnTime, rocket.secondStage.eng2.burnTime) > 0 and rocket.secondStage.fireStage:
        thrust = rocket.secondStage.ignition(altitude) * thrustMultiplier
        rocket.secondStage.mass = rocket.secondStage.mass - (rocket.secondStage.eng1FuelConsumption + rocket.secondStage.eng2FuelConsumption)
        if rocket.secondStage.eng2Count != 0 and (rocket.secondStage.eng2.burnTime >= 0.0 and rocket.secondStage.eng2.burnTime < -1.0):
          rocket.secondStage.eng2.shutDown()
          rocket.secondStage.eng2FuelConsumption = 0 
          addEventLog(queueList, queueTime, "Stage two secondary engine shut down")
        if (rocket.secondStage.eng1.burnTime <= 0 and rocket.secondStage.eng1.burnTime > -1.0):
          rocket.secondStage.eng1.shutDown()
          rocket.secondStage.eng1FuelConsumption = 0
          addEventLog(queueList, queueTime, "Stage two main engine shut down")
        if rocket.secondStage.hotSeparation and (rocket.secondStage.eng1.burnTime <= 2.0 and rocket.secondStage.eng1.burnTime >= 1.5) and not rocket.secondStage.runHotSeparation:
          addEventLog(queueList, queueTime, "Stage three ignition")
          rocket.secondStage.runHotSeparation = True
        if rocket.secondStage.runHotSeparation:
          thrust += rocket.thirdStage.ignition(altitude)
          rocket.thirdStage.mass = rocket.thirdStage.mass - (rocket.thirdStage.eng1FuelConsumption + rocket.thirdStage.eng2FuelConsumption)
        if rocket.secondStage.eng1.burnTime == -1 and rocket.secondStage.eng2.burnTime == -1: 
          rocket.secondStage.fireStage = False
          rocket.secondStage.readySeparate = True
          if rocket.thirdStage.eng1Count != 0:
            rocket.thirdStage.fireStage = True
            if not rocket.secondStage.hotSeparation:
              addEventLog(queueList, queueTime, "Stage three ignition")

      #Stage three activities:
      #Add third stage code here

      #Deploying payload:
      #In the future consider moving this to the top of the block that handles separation (this is so that deploying payload comes after separating the last stage)
      if not rocket.firstStage.fireStage and not rocket.secondStage.fireStage and not rocket.thirdStage.fireStage and not payloadDeployed: #max(rocket.firstStage.eng1.burnTime, rocket.firstStage.eng2.burnTime) == 0 and max(rocket.secondStage.eng1.burnTime, rocket.secondStage.eng2.burnTime) == 0 and max(rocket.thirdStage.eng1.burnTime, rocket.thirdStage.eng2.burnTime) == 0: 
        thrust = 0.0
        addEventLog(queueList, queueTime, f"{rocket.payload.name} deployed")
        payloadDeployed = True
      
      if payloadDeployed:
        launchCompleteTimer += 1

      if launchCompleteTimer == 300:
        programState = "end screen"

      mass = rocket.rocketMass()
      acceleration = rocket.findAcceleration(thrust, altitude, mass, velocity)
      if altitude >= 0:
        velocity += acceleration[0] * (1.0 / 20)
        yVelocity += acceleration[1] * (1.0 / 20)
        xVelocity += acceleration[2] * (1.0 / 20)
        altitude += yVelocity * (1.0 / 20)

      drawBlueBackground()
      displayModel(rocket, usedModels)
      printData(t, rocket, mass, acceleration[0], acceleration[2], acceleration[1], velocity, xVelocity, yVelocity, altitude, thrust, thrustMultiplier)
      printEventLog(queueList, queueTime)
    
    if programState == "end screen":
      programState = drawEndScreen(rocket, altitude, velocity)

    pygame.display.flip()
  pygame.quit()

if __name__ == "__main__":
    main()